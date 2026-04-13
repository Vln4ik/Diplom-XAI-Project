from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CRITICAL_TOKEN_RE = re.compile(r"https?://\S+|ОТСУТСТВУЕТ|\d+")
LETTER_RE = re.compile(r"[A-Za-zА-Яа-яЁё]")
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class LLMSettings:
    enabled: bool
    base_model: str
    adapter_path: str
    max_new_tokens: int
    temperature: float
    top_p: float
    repetition_penalty: float
    no_repeat_ngram_size: int
    num_candidates: int
    min_cyrillic_ratio: float
    local_files_only: bool


def read_llm_settings() -> LLMSettings:
    return LLMSettings(
        enabled=_env_flag("DIPLOM_LLM_ENABLED", False),
        base_model=os.getenv("DIPLOM_LLM_BASE_MODEL", "Qwen/Qwen2.5-0.5B-Instruct"),
        adapter_path=os.getenv("DIPLOM_LLM_ADAPTER", "data/models/sft-qwen05b-mixv3/adapter"),
        max_new_tokens=_env_int("DIPLOM_LLM_MAX_NEW_TOKENS", 140),
        temperature=_env_float("DIPLOM_LLM_TEMPERATURE", 0.35),
        top_p=_env_float("DIPLOM_LLM_TOP_P", 0.9),
        repetition_penalty=_env_float("DIPLOM_LLM_REPETITION_PENALTY", 1.12),
        no_repeat_ngram_size=_env_int("DIPLOM_LLM_NO_REPEAT_NGRAM_SIZE", 3),
        num_candidates=max(1, _env_int("DIPLOM_LLM_NUM_CANDIDATES", 3)),
        min_cyrillic_ratio=_env_float("DIPLOM_LLM_MIN_CYRILLIC_RATIO", 0.45),
        local_files_only=_env_flag("DIPLOM_LLM_LOCAL_FILES_ONLY", False),
    )


def _critical_tokens(text: str) -> list[str]:
    return CRITICAL_TOKEN_RE.findall(text)


def _preserves_critical_tokens(source: str, candidate: str) -> bool:
    source_tokens = _critical_tokens(source)
    if not source_tokens:
        return True
    return all(token in candidate for token in source_tokens)


def _extract_answer(decoded_text: str) -> str:
    text = decoded_text.strip()
    if "### Ответ:" in text:
        text = text.split("### Ответ:", 1)[1]
    if "\n### " in text:
        text = text.split("\n### ", 1)[0]
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _cyrillic_ratio(text: str) -> float:
    letters = LETTER_RE.findall(text)
    if not letters:
        return 0.0
    cyr = CYRILLIC_RE.findall(text)
    return len(cyr) / len(letters)


def _contains_literal(text: str, literal: str) -> bool:
    return literal.strip().lower() in text.lower()


def _required_literals(section_facts: list[dict[str, Any]]) -> list[str]:
    literals: list[str] = []
    seen: set[str] = set()
    for fact in section_facts:
        value = fact.get("value")
        if value in (None, ""):
            continue
        literal = str(value).strip()
        if len(literal) > 120:
            continue
        high_priority = bool(fact.get("required")) or bool(CRITICAL_TOKEN_RE.search(literal))
        if not high_priority:
            continue
        key = literal.lower()
        if key in seen:
            continue
        seen.add(key)
        literals.append(literal)
    return literals


def _prompt(section_title: str, source_text: str, section_facts: list[dict[str, Any]]) -> str:
    if section_facts:
        facts_lines = [
            f"- {fact.get('label', fact.get('field', 'поле'))}: {fact.get('value', 'ОТСУТСТВУЕТ')}"
            for fact in section_facts
        ]
        facts_text = "\n".join(facts_lines)
    else:
        facts_text = "- Нет извлеченных фактов"

    return (
        "### Инструкция:\n"
        "Перепиши фрагмент отчета в официально-деловом стиле.\n"
        "Не добавляй новых фактов. Сохрани все числовые значения, URL и слово ОТСУТСТВУЕТ без изменений.\n"
        "Верни только итоговый текст одного абзаца.\n\n"
        f"### Контекст:\nРаздел: {section_title}\nФакты:\n{facts_text}\nЧерновик: {source_text}\n\n"
        "### Ответ:\n"
    )


class _SectionRewriter:
    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings
        self.available = False
        self.reason = "not_initialized"
        self.device = "cpu"

        self._model = None
        self._tokenizer = None
        self._torch = None
        self._load()

    def _resolve_device(self, torch_module: Any) -> str:
        if torch_module.backends.mps.is_available():
            return "mps"
        if torch_module.cuda.is_available():
            return "cuda"
        return "cpu"

    def _load(self) -> None:
        adapter_dir = Path(self.settings.adapter_path)
        if not adapter_dir.exists():
            self.reason = f"adapter_not_found:{adapter_dir}"
            return

        try:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except Exception as exc:  # pragma: no cover - depends on optional env
            self.reason = f"deps_missing:{exc.__class__.__name__}"
            return

        self._torch = torch
        self.device = self._resolve_device(torch)

        try:
            tokenizer = AutoTokenizer.from_pretrained(
                self.settings.base_model,
                local_files_only=self.settings.local_files_only,
            )
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            base = AutoModelForCausalLM.from_pretrained(
                self.settings.base_model,
                local_files_only=self.settings.local_files_only,
            )
            model = PeftModel.from_pretrained(base, str(adapter_dir))
            model = model.to(self.device)
            model.eval()
        except Exception as exc:  # pragma: no cover - runtime env dependent
            self.reason = f"load_failed:{exc.__class__.__name__}"
            logger.exception("Failed to initialize local LLM rewriter")
            return

        self._tokenizer = tokenizer
        self._model = model
        self.available = True
        self.reason = "ok"

    def _score_candidate(self, source_text: str, candidate: str, required_literals: list[str]) -> tuple[float, str]:
        if not candidate:
            return -1.0, "empty_output"

        if len(candidate) < 24:
            return -1.0, "too_short"

        if not _preserves_critical_tokens(source_text, candidate):
            return -1.0, "critical_tokens_mismatch"

        cyr_ratio = _cyrillic_ratio(candidate)
        if cyr_ratio < self.settings.min_cyrillic_ratio:
            return -1.0, f"low_cyrillic_ratio:{cyr_ratio:.3f}"

        if required_literals:
            missing = [literal for literal in required_literals if not _contains_literal(candidate, literal)]
            if missing:
                return -1.0, f"missing_literals:{len(missing)}"

        compression_ratio = len(candidate) / max(1, len(source_text))
        if compression_ratio < 0.45:
            return -1.0, f"over_compressed:{compression_ratio:.3f}"

        score = 0.0
        score += min(cyr_ratio, 1.0)
        score += min(compression_ratio, 1.8) * 0.2
        score += min(len(candidate), 260) / 260 * 0.2
        return score, "ok"

    def rewrite(
        self,
        section_title: str,
        source_text: str,
        section_facts: list[dict[str, Any]],
    ) -> tuple[str, bool, str]:
        if not self.available:
            return source_text, False, self.reason

        prompt = _prompt(section_title, source_text, section_facts)
        required_literals = _required_literals(section_facts)
        try:
            encoded = self._tokenizer(prompt, return_tensors="pt")
            encoded = {name: tensor.to(self.device) for name, tensor in encoded.items()}

            with self._torch.no_grad():
                generated = self._model.generate(
                    **encoded,
                    max_new_tokens=self.settings.max_new_tokens,
                    do_sample=True,
                    temperature=self.settings.temperature,
                    top_p=self.settings.top_p,
                    repetition_penalty=self.settings.repetition_penalty,
                    no_repeat_ngram_size=self.settings.no_repeat_ngram_size,
                    num_return_sequences=self.settings.num_candidates,
                    pad_token_id=self._tokenizer.eos_token_id,
                    eos_token_id=self._tokenizer.eos_token_id,
                )
        except Exception as exc:  # pragma: no cover - runtime env dependent
            logger.exception("LLM rewrite failed for section %s", section_title)
            return source_text, False, f"generate_failed:{exc.__class__.__name__}"

        best_text = source_text
        best_score = -1.0
        best_reason = "no_valid_candidates"

        for idx in range(generated.size(0)):
            decoded = self._tokenizer.decode(generated[idx], skip_special_tokens=True)
            candidate = _extract_answer(decoded)
            score, reason = self._score_candidate(source_text, candidate, required_literals)
            if score > best_score:
                best_score = score
                best_reason = reason
                best_text = candidate if score >= 0 else source_text

        if best_score < 0:
            return source_text, False, best_reason

        return best_text, True, "ok"


@lru_cache(maxsize=6)
def _get_rewriter(
    base_model: str,
    adapter_path: str,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    repetition_penalty: float,
    no_repeat_ngram_size: int,
    num_candidates: int,
    min_cyrillic_ratio: float,
    local_files_only: bool,
) -> _SectionRewriter:
    settings = LLMSettings(
        enabled=True,
        base_model=base_model,
        adapter_path=adapter_path,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p,
        repetition_penalty=repetition_penalty,
        no_repeat_ngram_size=no_repeat_ngram_size,
        num_candidates=num_candidates,
        min_cyrillic_ratio=min_cyrillic_ratio,
        local_files_only=local_files_only,
    )
    return _SectionRewriter(settings)


def rewrite_sections_with_llm(
    sections: list[dict[str, Any]],
    section_facts_by_id: dict[str, list[dict[str, Any]]] | None = None,
    use_llm: bool | None = None,
) -> dict[str, Any]:
    settings = read_llm_settings()
    enabled = settings.enabled if use_llm is None else bool(use_llm)

    result = {
        "mode": "disabled",
        "enabled": enabled,
        "available": False,
        "applied_sections": 0,
        "reason": "llm_disabled",
        "model": settings.base_model,
        "adapter": str(Path(settings.adapter_path).resolve()),
        "rewrites": {},
    }
    if not enabled:
        return result

    rewriter = _get_rewriter(
        settings.base_model,
        settings.adapter_path,
        settings.max_new_tokens,
        settings.temperature,
        settings.top_p,
        settings.repetition_penalty,
        settings.no_repeat_ngram_size,
        settings.num_candidates,
        settings.min_cyrillic_ratio,
        settings.local_files_only,
    )
    result["available"] = rewriter.available
    result["reason"] = rewriter.reason
    if not rewriter.available:
        result["mode"] = "fallback"
        return result

    rewrites: dict[str, str] = {}
    applied_sections = 0
    failures = 0

    for section in sections:
        section_id = section["section_id"]
        section_facts = []
        if section_facts_by_id:
            section_facts = section_facts_by_id.get(section_id, [])
        text, applied, reason = rewriter.rewrite(section["title"], section["text"], section_facts)
        rewrites[section_id] = text
        if applied:
            applied_sections += 1
        else:
            failures += 1
            logger.info("LLM fallback for section %s: %s", section_id, reason)

    result["rewrites"] = rewrites
    result["applied_sections"] = applied_sections
    result["mode"] = "applied" if applied_sections > 0 else "fallback"
    if failures and applied_sections > 0:
        result["reason"] = f"partial:{applied_sections}_ok_{failures}_fallback"
    elif failures:
        result["reason"] = f"all_failed:{failures}"
    else:
        result["reason"] = "ok"
    return result
