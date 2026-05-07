from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def summarize(self, text: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate_section(self, title: str, context: str) -> str:
        raise NotImplementedError

    def status(self) -> dict[str, object]:
        return {"provider": self.provider_name}
