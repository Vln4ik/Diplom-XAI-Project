from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services.llm import read_llm_settings

logger = logging.getLogger(__name__)

KNOWN_MODEL_IDS = {
    "pipeline-basic",
    "general-assistant",
    "lora-rewriter",
    "full-analyst",
}

_ANSWER_SPLIT_RE = re.compile(r"###\s*Ответ:\s*", re.IGNORECASE)
_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _looks_like_repo_id(value: str) -> bool:
    if not value:
        return False
    if value.startswith(("/", "./", "../")):
        return False
    parts = value.split("/")
    if len(parts) != 2:
        return False
    return all(part.strip() for part in parts)


def _text_model_readiness(model_name_or_path: str, local_only: bool, not_found_reason: str) -> tuple[bool, str]:
    model_path = Path(model_name_or_path)
    is_repo_id = _looks_like_repo_id(model_name_or_path)
    if not model_path.exists() and not is_repo_id:
        return False, f"{not_found_reason}:{model_path.resolve()}"
    if local_only and not model_path.exists():
        return False, f"{not_found_reason}:{model_path.resolve()}"
    deps_ok, deps_reason = _has_optional_llm_deps(needs_peft=False)
    return deps_ok, deps_reason


def _has_optional_llm_deps(needs_peft: bool) -> tuple[bool, str]:
    try:
        import torch  # noqa: F401
        from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: F401
    except Exception as exc:  # pragma: no cover - runtime/env specific
        return False, f"deps_missing:{exc.__class__.__name__}"
    if not needs_peft:
        return True, "ok"
    try:
        from peft import PeftModel  # noqa: F401
    except Exception as exc:  # pragma: no cover - runtime/env specific
        return False, f"deps_missing:{exc.__class__.__name__}"
    return True, "ok"


@dataclass
class _TextRuntime:
    available: bool
    reason: str
    device: str = "cpu"
    tokenizer: Any = None
    model: Any = None
    torch: Any = None

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 220,
        temperature: float = 0.25,
        top_p: float = 0.9,
        do_sample: bool = True,
    ) -> tuple[str, bool, str]:
        if not self.available:
            return "", False, self.reason

        try:
            encoded = self.tokenizer(prompt, return_tensors="pt")
            encoded = {name: tensor.to(self.device) for name, tensor in encoded.items()}
            generation_kwargs = {
                "max_new_tokens": max_new_tokens,
                "repetition_penalty": 1.08,
                "no_repeat_ngram_size": 3,
                "pad_token_id": self.tokenizer.eos_token_id,
                "eos_token_id": self.tokenizer.eos_token_id,
                "do_sample": do_sample,
            }
            if do_sample:
                generation_kwargs["temperature"] = temperature
                generation_kwargs["top_p"] = top_p
            with self.torch.no_grad():
                output = self.model.generate(
                    **encoded,
                    **generation_kwargs,
                )
            decoded = self.tokenizer.decode(output[0], skip_special_tokens=True).strip()
        except Exception as exc:  # pragma: no cover - runtime/env specific
            logger.exception("Chat model generation failed")
            return "", False, f"generate_failed:{exc.__class__.__name__}"

        parts = _ANSWER_SPLIT_RE.split(decoded, maxsplit=1)
        if len(parts) == 2:
            decoded = parts[1].strip()
        if "\n###" in decoded:
            decoded = decoded.split("\n###", 1)[0].strip()
        decoded = _sanitize_model_output(decoded)
        if not decoded:
            return "", False, "empty_output"
        return decoded, True, "ok"


def _resolve_device(torch_module: Any) -> str:
    if torch_module.backends.mps.is_available():
        return "mps"
    if torch_module.cuda.is_available():
        return "cuda"
    return "cpu"


def _sanitize_model_output(text: str) -> str:
    cleaned = _CODE_FENCE_RE.sub("", text)
    cleaned = _INLINE_CODE_RE.sub(r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


@lru_cache(maxsize=3)
def _load_full_runtime(model_name_or_path: str, local_files_only: bool) -> _TextRuntime:
    deps_ok, deps_reason = _has_optional_llm_deps(needs_peft=False)
    if not deps_ok:
        return _TextRuntime(available=False, reason=deps_reason)

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as exc:  # pragma: no cover - runtime/env specific
        return _TextRuntime(available=False, reason=f"deps_missing:{exc.__class__.__name__}")

    device = _resolve_device(torch)
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name_or_path, local_files_only=local_files_only)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        model = AutoModelForCausalLM.from_pretrained(model_name_or_path, local_files_only=local_files_only)
        model = model.to(device)
        model.eval()
    except Exception as exc:  # pragma: no cover - runtime/env specific
        logger.exception("Failed to load full chat model")
        return _TextRuntime(available=False, reason=f"load_failed:{exc.__class__.__name__}")

    return _TextRuntime(
        available=True,
        reason="ok",
        device=device,
        tokenizer=tokenizer,
        model=model,
        torch=torch,
    )


@lru_cache(maxsize=3)
def _load_lora_runtime(base_model: str, adapter_path: str, local_files_only: bool) -> _TextRuntime:
    adapter = Path(adapter_path)
    if not adapter.exists():
        return _TextRuntime(available=False, reason=f"adapter_not_found:{adapter}")

    deps_ok, deps_reason = _has_optional_llm_deps(needs_peft=True)
    if not deps_ok:
        return _TextRuntime(available=False, reason=deps_reason)

    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as exc:  # pragma: no cover - runtime/env specific
        return _TextRuntime(available=False, reason=f"deps_missing:{exc.__class__.__name__}")

    device = _resolve_device(torch)
    try:
        tokenizer = AutoTokenizer.from_pretrained(base_model, local_files_only=local_files_only)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        base = AutoModelForCausalLM.from_pretrained(base_model, local_files_only=local_files_only)
        model = PeftModel.from_pretrained(base, str(adapter))
        model = model.to(device)
        model.eval()
    except Exception as exc:  # pragma: no cover - runtime/env specific
        logger.exception("Failed to load adapter chat model")
        return _TextRuntime(available=False, reason=f"load_failed:{exc.__class__.__name__}")

    return _TextRuntime(
        available=True,
        reason="ok",
        device=device,
        tokenizer=tokenizer,
        model=model,
        torch=torch,
    )


def resolve_model_id(model_id: str | None) -> str:
    raw = (model_id or "").strip()
    if raw in KNOWN_MODEL_IDS:
        return raw
    return "pipeline-basic"


def model_uses_lora_rewriter(model_id: str) -> bool:
    return resolve_model_id(model_id) == "lora-rewriter"


def _model_readiness(model_id: str) -> tuple[bool, str]:
    llm = read_llm_settings()
    full_path = os.getenv("DIPLOM_FULL_MODEL", "data/models/full-qwen05b-report")
    general_model = os.getenv("DIPLOM_CHAT_GENERAL_MODEL", llm.base_model)
    local_only = _env_flag("DIPLOM_CHAT_LOCAL_FILES_ONLY", llm.local_files_only)
    model_id = resolve_model_id(model_id)

    if model_id == "pipeline-basic":
        return True, "ok"
    if model_id == "general-assistant":
        return _text_model_readiness(general_model, local_only, "general_model_not_found")
    if model_id == "lora-rewriter":
        if not Path(llm.adapter_path).exists():
            return False, f"adapter_not_found:{Path(llm.adapter_path).resolve()}"
        deps_ok, deps_reason = _has_optional_llm_deps(needs_peft=True)
        return deps_ok, deps_reason

    return _text_model_readiness(full_path, local_only, "full_model_not_found")


def list_chat_models() -> list[dict[str, Any]]:
    llm = read_llm_settings()
    full_path = os.getenv("DIPLOM_FULL_MODEL", "data/models/full-qwen05b-report")
    general_model = os.getenv("DIPLOM_CHAT_GENERAL_MODEL", llm.base_model)

    items = [
        {
            "id": "pipeline-basic",
            "title": "Pipeline Basic",
            "description": "Детерминированный режим (извлечение, генерация по шаблону, XAI-метрики).",
        },
        {
            "id": "general-assistant",
            "title": "General Assistant",
            "description": f"Стандартная языковая модель для базовых вопросов: {general_model}.",
        },
        {
            "id": "lora-rewriter",
            "title": "LoRA Rewriter",
            "description": f"База {llm.base_model} + адаптер {Path(llm.adapter_path).name}.",
        },
        {
            "id": "full-analyst",
            "title": "Full Analyst Model",
            "description": f"Полная локальная модель для аналитического ответа: {full_path}.",
        },
    ]

    enriched: list[dict[str, Any]] = []
    for item in items:
        available, reason = _model_readiness(item["id"])
        enriched.append(
            {
                **item,
                "available": available,
                "reason": reason,
            }
        )
    return enriched


def _format_context_for_model(message: str, report_context: str) -> str:
    clipped_context = report_context.strip()
    if len(clipped_context) > 3800:
        clipped_context = clipped_context[:3800] + "\n...[context truncated]"
    return (
        "### Инструкция:\n"
        "Ты аналитическая модель для объяснимых отчетов.\n"
        "Проанализируй контекст и ответь структурно и по делу.\n"
        "Не выдумывай факты, которых нет в контексте.\n\n"
        f"### Запрос пользователя:\n{message.strip()}\n\n"
        f"### Контекст отчета:\n{clipped_context}\n\n"
        "### Ответ:\n"
    )


def _format_general_prompt(message: str, report_context: str) -> str:
    context = report_context.strip()
    if len(context) > 2200:
        context = context[:2200] + "\n...[context truncated]"
    context_block = ""
    if context:
        context_block = f"### Дополнительный контекст:\n{context}\n\n"
    return (
        "### Инструкция:\n"
        "Ты стандартная языковая модель-помощник.\n"
        "Отвечай по-русски, просто и по существу.\n"
        "Если данных мало, задай один уточняющий вопрос.\n\n"
        f"### Вопрос пользователя:\n{message.strip()}\n\n"
        f"{context_block}"
        "### Ответ:\n"
    )


def _heuristic_analysis(message: str, report_context: str) -> str:
    lower = message.lower()
    lines: list[str] = []
    lines.append("Анализ выполнен в детерминированном режиме.")
    if "score_conf" in report_context.lower():
        lines.append("Проверьте разделы с низким Score_conf и статусом requires_review.")
    if "отсутствует" in report_context.lower():
        lines.append("Есть незаполненные поля: дополните документы, чтобы убрать маркеры ОТСУТСТВУЕТ.")
    if any(token in lower for token in ("улучш", "качест", "дообуч")):
        lines.append("Для улучшения качества: расширьте SFT-датасет и повышайте долю доменных примеров.")
    if len(lines) == 1:
        lines.append("Сформулируйте уточняющий запрос: что именно оценить (риски, полнота, соответствие нормам).")
    return "\n".join(lines)


def _heuristic_general_answer(message: str) -> str:
    lower = message.lower().strip()
    if not lower:
        return "Сформулируйте вопрос, и я отвечу по существу."
    if "сколько пальцев" in lower and "челов" in lower:
        return "У человека обычно 20 пальцев: 10 на руках и 10 на ногах."
    if any(token in lower for token in ("привет", "здравств", "hello", "hi")):
        return "Привет. Задайте любой базовый текстовый вопрос, и я отвечу кратко."
    if "что такое" in lower:
        return "Это базовый режим без загруженной языковой модели. Уточните область, и я дам структурное объяснение."
    return "Базовый ответ в fallback-режиме: уточните вопрос или подключите стандартную языковую модель."


def _direct_general_fact_answer(message: str) -> str | None:
    lower = message.lower().strip()
    if "сколько пальцев" in lower and "челов" in lower:
        if "на руке" in lower:
            return "На одной руке у человека обычно 5 пальцев."
        if "на руках" in lower:
            return "На двух руках у человека обычно 10 пальцев."
        if "на ноге" in lower:
            return "На одной ноге у человека обычно 5 пальцев."
        if "на ногах" in lower:
            return "На двух ногах у человека обычно 10 пальцев."
        return "У человека обычно 20 пальцев: 10 на руках и 10 на ногах."
    return None


def generate_model_analysis(
    model_id: str,
    message: str,
    report_context: str,
) -> dict[str, Any]:
    selected = resolve_model_id(model_id)
    llm = read_llm_settings()
    full_model = os.getenv("DIPLOM_FULL_MODEL", "data/models/full-qwen05b-report")
    general_model = os.getenv("DIPLOM_CHAT_GENERAL_MODEL", llm.base_model)
    local_only = _env_flag("DIPLOM_CHAT_LOCAL_FILES_ONLY", llm.local_files_only)

    if selected == "pipeline-basic":
        return {
            "text": _heuristic_analysis(message, report_context),
            "model_id": selected,
            "applied": False,
            "reason": "heuristic_mode",
        }

    if selected == "general-assistant":
        direct_answer = _direct_general_fact_answer(message)
        if direct_answer:
            return {
                "text": direct_answer,
                "model_id": selected,
                "applied": False,
                "reason": "rule_based_fact",
            }
        prompt = _format_general_prompt(message, report_context)
        runtime = _load_full_runtime(general_model, local_only)
    elif selected == "lora-rewriter":
        prompt = _format_context_for_model(message, report_context)
        runtime = _load_lora_runtime(llm.base_model, llm.adapter_path, local_only)
    else:
        prompt = _format_context_for_model(message, report_context)
        runtime = _load_full_runtime(full_model, local_only)

    output, ok, reason = runtime.generate(
        prompt,
        do_sample=selected != "general-assistant",
    )
    if ok:
        return {
            "text": output,
            "model_id": selected,
            "applied": True,
            "reason": "ok",
        }

    fallback_text = _heuristic_analysis(message, report_context)
    if selected == "general-assistant":
        fallback_text = _heuristic_general_answer(message)

    return {
        "text": fallback_text,
        "model_id": selected,
        "applied": False,
        "reason": reason,
    }
