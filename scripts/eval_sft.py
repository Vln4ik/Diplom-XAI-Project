from __future__ import annotations

import argparse
import math

import torch
from datasets import load_dataset
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


def resolve_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def format_prompt(instruction: str, context: str) -> str:
    instruction = instruction.strip()
    context = context.strip()
    if context:
        return f"### Инструкция:\n{instruction}\n\n### Контекст:\n{context}\n\n### Ответ:\n"
    return f"### Инструкция:\n{instruction}\n\n### Ответ:\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate base model or base+adapter on SFT dataset")
    parser.add_argument("--dataset", default="data/processed/sft_dataset_dolly2k.jsonl")
    parser.add_argument("--base-model", default="ai-forever/rugpt3small_based_on_gpt2")
    parser.add_argument("--adapter", default="")
    parser.add_argument("--max-length", type=int, default=192)
    parser.add_argument("--eval-samples", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--response-only-loss", action="store_true")
    args = parser.parse_args()

    device = resolve_device()

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base = AutoModelForCausalLM.from_pretrained(args.base_model)
    if args.adapter:
        model = PeftModel.from_pretrained(base, args.adapter)
    else:
        model = base

    model = model.to(device)
    model.eval()

    ds = load_dataset("json", data_files=args.dataset, split="train")
    n = min(args.eval_samples, len(ds))
    ds = ds.select(range(n))

    losses: list[float] = []
    with torch.no_grad():
        for i in range(0, len(ds), args.batch_size):
            batch = ds[i : i + args.batch_size]
            rows = batch["text"]
            encoded = tokenizer(
                rows,
                truncation=True,
                padding=True,
                max_length=args.max_length,
                return_tensors="pt",
            ).to(device)

            labels = encoded["input_ids"].clone()

            if args.response_only_loss:
                for j in range(len(rows)):
                    instruction = str(batch.get("instruction", [""])[j])
                    context = str(batch.get("context", [""])[j])
                    prompt = format_prompt(instruction, context)
                    prompt_len = len(tokenizer(prompt, add_special_tokens=False)["input_ids"])
                    prompt_len = min(prompt_len, labels[j].shape[0])
                    labels[j, :prompt_len] = -100

            labels[encoded["attention_mask"] == 0] = -100

            outputs = model(**encoded, labels=labels)
            losses.append(float(outputs.loss.item()))

    mean_loss = sum(losses) / max(1, len(losses))
    ppl = math.exp(mean_loss) if mean_loss < 20 else float("inf")

    print(f"eval_samples={n}")
    print(f"mean_loss={mean_loss:.4f}")
    print(f"perplexity={ppl:.4f}")


if __name__ == "__main__":
    main()
