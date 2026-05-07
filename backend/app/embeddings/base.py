from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Sequence


def normalize_vector(values: Sequence[float]) -> list[float]:
    vector = [float(value) for value in values]
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [round(value / norm, 6) for value in vector]


def resize_vector(values: Sequence[float], target_size: int) -> list[float]:
    if target_size <= 0:
        raise ValueError("target_size must be positive")

    source = [float(value) for value in values]
    if not source:
        return [0.0] * target_size
    if len(source) == target_size:
        return source
    if len(source) < target_size:
        return source + [0.0] * (target_size - len(source))

    resized: list[float] = []
    source_size = len(source)
    for index in range(target_size):
        start = round(index * source_size / target_size)
        end = round((index + 1) * source_size / target_size)
        if end <= start:
            end = min(source_size, start + 1)
        chunk = source[start:end] or [source[min(start, source_size - 1)]]
        resized.append(sum(chunk) / len(chunk))
    return resized


def adapt_vector(values: Sequence[float], target_size: int) -> list[float]:
    return normalize_vector(resize_vector(values, target_size))


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError

    def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]

    def status(self) -> dict[str, object]:
        return {"provider": self.provider_name}
