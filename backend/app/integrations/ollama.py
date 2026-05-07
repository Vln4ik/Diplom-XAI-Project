from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


class OllamaError(RuntimeError):
    pass


def _endpoint(base_url: str, path: str) -> str:
    normalized = base_url.rstrip("/") + "/"
    return urljoin(normalized, path.lstrip("/"))


def request_json(
    *,
    method: str,
    base_url: str,
    path: str,
    timeout: float,
    payload: dict | None = None,
) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(_endpoint(base_url, path), data=data, headers=headers, method=method.upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:  # pragma: no cover - depends on runtime IO
        detail = exc.read().decode("utf-8", errors="ignore")
        raise OllamaError(f"Ollama HTTP {exc.code}: {detail or exc.reason}") from exc
    except URLError as exc:  # pragma: no cover - depends on runtime IO
        raise OllamaError(f"Ollama connection failed: {exc.reason}") from exc
    except TimeoutError as exc:  # pragma: no cover - depends on runtime IO
        raise OllamaError("Ollama request timed out") from exc

    if not raw.strip():
        return {}

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        last_payload = {}
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                last_payload = json.loads(line)
            except json.JSONDecodeError:
                continue
        if last_payload:
            return last_payload
        raise OllamaError("Ollama returned non-JSON payload")


def list_models(base_url: str, timeout: float) -> list[str]:
    payload = request_json(method="GET", base_url=base_url, path="/tags", timeout=timeout)
    models = payload.get("models", [])
    names: list[str] = []
    for item in models:
        if isinstance(item, dict):
            name = item.get("name") or item.get("model")
            if isinstance(name, str):
                names.append(name)
    return names


def has_model(available_models: list[str] | None, configured_model: str) -> bool:
    if not available_models:
        return False

    configured = configured_model.strip()
    configured_base = configured.removesuffix(":latest")
    for name in available_models:
        candidate = name.strip()
        if candidate == configured:
            return True
        if candidate.removesuffix(":latest") == configured_base:
            return True
    return False
