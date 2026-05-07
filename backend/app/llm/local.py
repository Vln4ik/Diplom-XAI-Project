from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.integrations.ollama import OllamaError, has_model, list_models, request_json
from app.llm.base import LLMProvider


class DeterministicFallbackLLMProvider(LLMProvider):
    @property
    def provider_name(self) -> str:
        return "template-fallback"

    def summarize(self, text: str) -> str:
        normalized = " ".join(text.split())
        return normalized[:500]

    def generate_section(self, title: str, context: str) -> str:
        normalized_context = context.strip()
        if not normalized_context:
            normalized_context = "Недостаточно данных для автоматической генерации раздела."
        return f"{title}\n\n{normalized_context[:1200]}".strip()

    def status(self) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "mode": "fallback",
        }


class LocalTransformersProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.model_path = settings.local_llm_model_path
        self.model_name = settings.local_llm_model_name
        self.task = settings.local_llm_task
        self.max_input_chars = settings.local_llm_max_input_chars
        self.summary_max_new_tokens = settings.local_llm_summary_max_new_tokens
        self.section_max_new_tokens = settings.local_llm_section_max_new_tokens
        self._generator = None
        self._load_attempted = False
        self._load_error: str | None = None
        self._fallback = DeterministicFallbackLLMProvider()

    @property
    def provider_name(self) -> str:
        return "local-transformers"

    def _model_source(self) -> str | None:
        return self.model_path or self.model_name

    def _ensure_generator(self):
        if self._generator is not None:
            return self._generator
        if self._load_attempted:
            return None

        self._load_attempted = True
        source = self._model_source()
        if not source:
            self._load_error = "Local LLM model is not configured."
            return None

        try:
            from transformers import pipeline
        except Exception as exc:  # pragma: no cover - depends on optional runtime package
            self._load_error = f"transformers is unavailable: {exc}"
            return None

        try:
            self._generator = pipeline(
                self.task,
                model=source,
                tokenizer=source,
                device_map="auto",
                model_kwargs={"torch_dtype": "auto"},
            )
        except TypeError:  # pragma: no cover - compatibility fallback
            try:
                self._generator = pipeline(self.task, model=source, tokenizer=source)
            except Exception as exc:
                self._load_error = str(exc)
                self._generator = None
        except Exception as exc:  # pragma: no cover - depends on model availability
            self._load_error = str(exc)
            self._generator = None
        return self._generator

    def _run_generation(self, prompt: str, *, max_new_tokens: int) -> str | None:
        generator = self._ensure_generator()
        if generator is None:
            return None

        generation_kwargs: dict[str, object] = {
            "max_new_tokens": max_new_tokens,
            "do_sample": False,
            "truncation": True,
        }
        if self.task == "text-generation":
            generation_kwargs["return_full_text"] = False

        try:
            response = generator(prompt[: self.max_input_chars], **generation_kwargs)
        except TypeError:  # pragma: no cover - pipeline signatures vary
            response = generator(prompt[: self.max_input_chars], max_new_tokens=max_new_tokens, do_sample=False)
        except Exception:  # pragma: no cover - depends on model runtime
            return None

        if isinstance(response, list) and response:
            payload = response[0]
            if isinstance(payload, dict):
                for key in ("generated_text", "summary_text", "text"):
                    if key in payload and payload[key]:
                        return str(payload[key]).strip()
        return None

    def summarize(self, text: str) -> str:
        prompt = (
            "Сделай краткое русскоязычное резюме документа для подготовки регуляторного отчета. "
            "Выдели только факты и подтверждения.\n\n"
            f"Текст:\n{text}"
        )
        generated = self._run_generation(prompt, max_new_tokens=self.summary_max_new_tokens)
        return generated[:1000] if generated else self._fallback.summarize(text)

    def generate_section(self, title: str, context: str) -> str:
        prompt = (
            "Сформируй раздел отчета на русском языке. "
            "Используй деловой тон, не выдумывай факты и опирайся только на переданный контекст.\n\n"
            f"Раздел: {title}\n"
            f"Контекст:\n{context}"
        )
        generated = self._run_generation(prompt, max_new_tokens=self.section_max_new_tokens)
        return generated if generated else self._fallback.generate_section(title, context)

    def status(self) -> dict[str, object]:
        mode = "model" if self._generator is not None else "fallback"
        return {
            "provider": self.provider_name,
            "configured_model": self._model_source(),
            "task": self.task,
            "load_attempted": self._load_attempted,
            "loaded": self._generator is not None,
            "mode": mode,
            "fallback_provider": self._fallback.provider_name,
            "load_error": self._load_error,
        }


class OllamaLLMProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.ollama_base_url
        self.model_name = settings.ollama_llm_model
        self.timeout = settings.ollama_request_timeout_seconds
        self.keep_alive = settings.ollama_keep_alive
        self.summary_max_new_tokens = settings.local_llm_summary_max_new_tokens
        self.section_max_new_tokens = settings.local_llm_section_max_new_tokens
        self._fallback = DeterministicFallbackLLMProvider()
        self._last_error: str | None = None

    @property
    def provider_name(self) -> str:
        return "ollama"

    def _generate(self, *, prompt: str, system: str, max_tokens: int) -> str | None:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {"num_predict": max_tokens},
        }
        try:
            response = request_json(
                method="POST",
                base_url=self.base_url,
                path="/generate",
                timeout=self.timeout,
                payload=payload,
            )
        except OllamaError as exc:
            self._last_error = str(exc)
            return None

        result = response.get("response")
        if isinstance(result, str) and result.strip():
            self._last_error = None
            return result.strip()
        self._last_error = "Ollama returned empty generation payload."
        return None

    def summarize(self, text: str) -> str:
        generated = self._generate(
            prompt=text[:4000],
            system=(
                "Сделай краткое русскоязычное резюме документа для подготовки регуляторного отчета. "
                "Оставляй только факты, требования и подтверждения."
            ),
            max_tokens=self.summary_max_new_tokens,
        )
        return generated[:1000] if generated else self._fallback.summarize(text)

    def generate_section(self, title: str, context: str) -> str:
        generated = self._generate(
            prompt=f"Раздел: {title}\nКонтекст:\n{context[:4000]}",
            system=(
                "Сформируй деловой раздел отчета на русском языке. "
                "Не выдумывай факты, опирайся только на переданный контекст."
            ),
            max_tokens=self.section_max_new_tokens,
        )
        return generated if generated else self._fallback.generate_section(title, context)

    def status(self) -> dict[str, object]:
        available_models: list[str] | None = None
        reachable = False
        check_error: str | None = None
        try:
            available_models = list_models(self.base_url, self.timeout)
            reachable = True
        except OllamaError as exc:
            check_error = str(exc)
        model_available = has_model(available_models, self.model_name)

        return {
            "provider": self.provider_name,
            "configured_model": self.model_name,
            "base_url": self.base_url,
            "reachable": reachable,
            "model_available": model_available,
            "available_models": available_models,
            "mode": "model" if reachable and model_available else "fallback",
            "fallback_provider": self._fallback.provider_name,
            "load_error": self._last_error or check_error,
        }


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    provider = get_settings().llm_provider.lower()
    if provider == "ollama":
        return OllamaLLMProvider()
    if provider in {"local", "local_transformers", "local-transformers", "transformers"}:
        return LocalTransformersProvider()
    return DeterministicFallbackLLMProvider()


def describe_llm_provider() -> dict[str, object]:
    return get_llm_provider().status()
