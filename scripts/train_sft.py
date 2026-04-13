from __future__ import annotations

import argparse
from pathlib import Path

import torch
from datasets import Dataset, load_dataset
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    default_data_collator,
)


def resolve_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def detect_lora_targets(model: torch.nn.Module) -> list[str]:
    preferred = [
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
        "c_attn",
        "c_proj",
    ]
    names = [name for name, _ in model.named_modules()]

    detected: list[str] = []
    for target in preferred:
        if any(name.endswith(target) for name in names):
            detected.append(target)

    if detected:
        return detected

    for name in names:
        tail = name.split(".")[-1]
        if "proj" in tail or "attn" in tail:
            detected.append(tail)
        if len(set(detected)) >= 2:
            break

    return list(dict.fromkeys(detected)) or ["c_attn"]


def format_prompt(instruction: str, context: str) -> str:
    instruction = instruction.strip()
    context = context.strip()
    if context:
        return f"### Инструкция:\n{instruction}\n\n### Контекст:\n{context}\n\n### Ответ:\n"
    return f"### Инструкция:\n{instruction}\n\n### Ответ:\n"


def build_tokenized_dataset(raw_ds: Dataset, tokenizer: AutoTokenizer, max_length: int) -> Dataset:
    def to_item(row: dict) -> dict:
        instruction = str(row.get("instruction", ""))
        context = str(row.get("context", ""))
        response = str(row.get("response", ""))

        prompt = format_prompt(instruction, context)
        full_text = prompt + response

        prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        full = tokenizer(
            full_text,
            add_special_tokens=False,
            truncation=True,
            max_length=max_length,
        )
        input_ids = full["input_ids"]
        attention_mask = full["attention_mask"]

        labels = input_ids.copy()
        prompt_len = min(len(prompt_ids), len(labels))
        for i in range(prompt_len):
            labels[i] = -100

        pad_token = tokenizer.pad_token_id
        if pad_token is None:
            pad_token = tokenizer.eos_token_id

        pad_len = max_length - len(input_ids)
        if pad_len > 0:
            input_ids = input_ids + [pad_token] * pad_len
            attention_mask = attention_mask + [0] * pad_len
            labels = labels + [-100] * pad_len

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }

    tokenized = raw_ds.map(to_item, remove_columns=raw_ds.column_names)
    return tokenized


def main() -> None:
    parser = argparse.ArgumentParser(description="LoRA SFT training with response-only loss")
    parser.add_argument("--dataset", default="data/processed/sft_dataset.jsonl")
    parser.add_argument("--model", default="ai-forever/rugpt3small_based_on_gpt2")
    parser.add_argument("--output", default="data/models/sft-rugpt3small")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--warmup-steps", type=int, default=20)
    parser.add_argument("--save-steps", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--eval-ratio", type=float, default=0.05)
    parser.add_argument("--init-adapter", default="")
    args = parser.parse_args()

    device = resolve_device()
    print(f"Using device: {device}")

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(args.model)
    lora_targets = detect_lora_targets(base_model)
    print(f"LoRA target modules: {lora_targets}")

    if args.init_adapter:
        print(f"Loading existing adapter for continued training: {args.init_adapter}")
        model = PeftModel.from_pretrained(base_model, args.init_adapter, is_trainable=True)
    else:
        peft_config = LoraConfig(
            r=args.lora_r,
            lora_alpha=args.lora_alpha,
            lora_dropout=args.lora_dropout,
            target_modules=lora_targets,
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(base_model, peft_config)

    raw_ds = load_dataset("json", data_files=args.dataset, split="train")
    print(f"Loaded rows: {len(raw_ds)}")
    tokenized = build_tokenized_dataset(raw_ds, tokenizer, args.max_length)

    eval_ds = None
    if 0.0 < args.eval_ratio < 1.0 and len(tokenized) > 200:
        split = tokenized.train_test_split(test_size=args.eval_ratio, seed=args.seed)
        train_ds = split["train"]
        eval_ds = split["test"]
    else:
        train_ds = tokenized

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    use_fp16 = device == "cuda"

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        warmup_steps=args.warmup_steps,
        logging_steps=10,
        save_steps=args.save_steps,
        save_total_limit=3,
        max_steps=args.max_steps,
        report_to="none",
        fp16=use_fp16,
        bf16=False,
        dataloader_num_workers=0,
        remove_unused_columns=False,
        seed=args.seed,
        optim="adamw_torch",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=default_data_collator,
    )

    trainer.train()

    if eval_ds is not None:
        metrics = trainer.evaluate()
        print(f"Eval metrics: {metrics}")

    trainer.save_model(str(output_dir / "adapter"))
    tokenizer.save_pretrained(str(output_dir / "adapter"))

    print(f"Training finished. Adapter saved to: {output_dir / 'adapter'}")


if __name__ == "__main__":
    main()
