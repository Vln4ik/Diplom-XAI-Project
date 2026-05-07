#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import mimetypes
import subprocess
import sys
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.performance import (  # noqa: E402
    flatten_timing_metrics,
    parse_memory_to_mib,
    parse_percentage,
    success_rate,
    summarize_resource_samples,
    throughput_per_minute,
)

SAMPLES_DIR = PROJECT_ROOT / "samples" / "documents"
SAMPLE_DOCUMENTS = [
    ("rosobrnadzor_sample.txt", "normative"),
    ("rosobrnadzor_evidence_site.txt", "evidence"),
    ("organization_profile.json", "other"),
    ("education_metrics.csv", "data_table"),
]


class ApiError(RuntimeError):
    pass


class DockerResourceSampler:
    def __init__(
        self,
        *,
        compose_file: Path,
        services: list[str],
        interval_seconds: float,
    ) -> None:
        self.compose_file = compose_file
        self.services = services
        self.interval_seconds = interval_seconds
        self.samples: list[dict[str, object]] = []
        self.errors: list[str] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._containers = self._discover_containers()

    def _discover_containers(self) -> dict[str, str]:
        command = [
            "docker",
            "compose",
            "-f",
            str(self.compose_file),
            "ps",
            "--format",
            "json",
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        containers: dict[str, str] = {}
        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                continue
            service_name = str(payload.get("Service") or "").strip()
            container_name = str(payload.get("Name") or "").strip()
            state = str(payload.get("State") or "").strip().lower()
            if service_name and container_name and state == "running":
                containers[service_name] = container_name
        filtered = {service: containers[service] for service in self.services if service in containers}
        if not filtered:
            raise RuntimeError("No running Docker containers matched the requested resource services")
        return filtered

    def _collect_once(self) -> dict[str, object]:
        container_names = list(self._containers.values())
        command = ["docker", "stats", "--no-stream", "--format", "{{json .}}", *container_names]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        name_to_service = {name: service for service, name in self._containers.items()}
        containers_payload: dict[str, dict[str, float]] = {}

        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                continue
            container_name = str(payload.get("Name") or "").strip()
            service_name = name_to_service.get(container_name)
            if not service_name:
                continue
            memory_usage = str(payload.get("MemUsage") or "")
            used_memory_raw = memory_usage.split("/", 1)[0].strip() if memory_usage else ""
            containers_payload[service_name] = {
                "cpu_percent": parse_percentage(payload.get("CPUPerc")),
                "memory_mib": parse_memory_to_mib(used_memory_raw),
                "memory_percent": parse_percentage(payload.get("MemPerc")),
                "pids": float(str(payload.get("PIDs") or "0").strip() or "0"),
            }

        return {
            "captured_at": datetime.now(UTC).isoformat(),
            "containers": containers_payload,
        }

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.samples.append(self._collect_once())
            except Exception as exc:  # pragma: no cover - runtime protection
                self.errors.append(str(exc))
            if self._stop_event.wait(self.interval_seconds):
                break

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="docker-resource-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(2.0, self.interval_seconds * 2))

    def to_payload(self, *, include_samples: bool) -> dict[str, object]:
        payload: dict[str, object] = {
            "mode": "docker",
            "compose_file": str(self.compose_file),
            "services": self.services,
            "resolved_containers": self._containers,
            "sample_interval_seconds": self.interval_seconds,
            "sample_count": len(self.samples),
            "summary": summarize_resource_samples(self.samples),
        }
        if include_samples:
            payload["samples"] = self.samples
        if self.errors:
            payload["errors"] = self.errors
        return payload


def _request(
    *,
    method: str,
    url: str,
    timeout: float,
    headers: dict[str, str] | None = None,
    json_payload: dict | None = None,
    form_fields: dict[str, str] | None = None,
    files: list[tuple[str, str, bytes, str]] | None = None,
) -> object:
    request_headers = {"Accept": "application/json", **(headers or {})}
    body: bytes | None = None
    if json_payload is not None:
        body = json.dumps(json_payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    elif form_fields is not None or files is not None:
        body, content_type = _encode_multipart(form_fields or {}, files or [])
        request_headers["Content-Type"] = content_type

    request = Request(url, data=body, headers=request_headers, method=method.upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise ApiError(f"{method} {url} -> HTTP {exc.code}: {detail or exc.reason}") from exc
    except URLError as exc:
        raise ApiError(f"{method} {url} -> connection failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ApiError(f"{method} {url} -> timed out") from exc

    if not raw.strip():
        return {}
    return json.loads(raw)


def _encode_multipart(fields: dict[str, str], files: list[tuple[str, str, bytes, str]]) -> tuple[bytes, str]:
    boundary = f"----xai-benchmark-{uuid.uuid4().hex}"
    lines: list[bytes] = []

    for name, value in fields.items():
        lines.extend(
            [
                f"--{boundary}".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"'.encode("utf-8"),
                b"",
                value.encode("utf-8"),
            ]
        )

    for field_name, filename, content, content_type in files:
        lines.extend(
            [
                f"--{boundary}".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"'
                ).encode("utf-8"),
                f"Content-Type: {content_type}".encode("utf-8"),
                b"",
                content,
            ]
        )

    lines.append(f"--{boundary}--".encode("utf-8"))
    lines.append(b"")
    body = b"\r\n".join(lines)
    return body, f"multipart/form-data; boundary={boundary}"


def _timed(callable_):
    started = time.perf_counter()
    result = callable_()
    return result, round(time.perf_counter() - started, 4)


def _poll(
    fetch,
    *,
    timeout_seconds: float,
    interval_seconds: float,
    is_ready,
) -> tuple[object, float]:
    started = time.perf_counter()
    while True:
        result = fetch()
        if is_ready(result):
            return result, round(time.perf_counter() - started, 4)
        if time.perf_counter() - started >= timeout_seconds:
            raise TimeoutError("Polling timed out")
        time.sleep(interval_seconds)


def _api_url(base_url: str, path: str, params: dict[str, str] | None = None) -> str:
    normalized = base_url.rstrip("/")
    if params:
        return f"{normalized}{path}?{urlencode(params)}"
    return f"{normalized}{path}"


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _run_single_benchmark_run(args: argparse.Namespace, run_index: int) -> dict[str, object]:
    run_started = time.perf_counter()
    login_payload, login_seconds = _timed(
        lambda: _request(
            method="POST",
            url=_api_url(args.base_url, "/api/auth/login"),
            timeout=args.request_timeout,
            json_payload={"email": args.email, "password": args.password},
        )
    )
    if not isinstance(login_payload, dict) or "access_token" not in login_payload:
        raise ApiError("Login response does not contain access_token")
    token = str(login_payload["access_token"])
    headers = _auth_headers(token)

    run_label = f"benchmark-org-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{run_index}-{uuid.uuid4().hex[:6]}"
    timings: dict[str, float] = {"login": login_seconds}

    organization_payload, timings["create_organization"] = _timed(
        lambda: _request(
            method="POST",
            url=_api_url(args.base_url, "/api/organizations"),
            timeout=args.request_timeout,
            headers=headers,
            json_payload={"name": run_label, "organization_type": "educational"},
        )
    )
    if not isinstance(organization_payload, dict):
        raise ApiError("Organization response must be an object")
    organization_id = str(organization_payload["id"])

    document_ids: list[str] = []
    upload_total_started = time.perf_counter()
    for filename, category in SAMPLE_DOCUMENTS:
        sample_path = SAMPLES_DIR / filename
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        upload_payload, upload_seconds = _timed(
            lambda sample_path=sample_path, filename=filename, category=category, content_type=content_type: _request(
                method="POST",
                url=_api_url(args.base_url, f"/api/organizations/{organization_id}/documents"),
                timeout=args.request_timeout,
                headers=headers,
                form_fields={"category": category},
                files=[("files", filename, sample_path.read_bytes(), content_type)],
            )
        )
        timings[f"upload_{filename}"] = upload_seconds
        if not isinstance(upload_payload, list) or not upload_payload:
            raise ApiError(f"Upload response for {filename} is empty")
        document_ids.append(str(upload_payload[0]["id"]))
    timings["upload_total"] = round(time.perf_counter() - upload_total_started, 4)

    process_total_started = time.perf_counter()
    document_statuses: dict[str, str] = {}
    for document_id, (filename, _category) in zip(document_ids, SAMPLE_DOCUMENTS, strict=True):
        _request(
            method="POST",
            url=_api_url(args.base_url, f"/api/documents/{document_id}/process"),
            timeout=args.request_timeout,
            headers=headers,
        )
        document_payload, process_seconds = _poll(
            lambda document_id=document_id: _request(
                method="GET",
                url=_api_url(args.base_url, f"/api/documents/{document_id}"),
                timeout=args.request_timeout,
                headers=headers,
            ),
            timeout_seconds=args.pipeline_timeout,
            interval_seconds=args.poll_interval,
            is_ready=lambda payload: isinstance(payload, dict)
            and payload.get("status") in {"processed", "requires_review", "failed"},
        )
        timings[f"process_{filename}"] = process_seconds
        if not isinstance(document_payload, dict):
            raise ApiError("Document payload must be an object")
        document_statuses[filename] = str(document_payload["status"])
    timings["process_total"] = round(time.perf_counter() - process_total_started, 4)

    search_payload, timings["search"] = _timed(
        lambda: _request(
            method="GET",
            url=_api_url(
                args.base_url,
                f"/api/organizations/{organization_id}/documents/search",
                params={"query": args.query, "limit": "10"},
            ),
            timeout=args.request_timeout,
            headers=headers,
        )
    )
    if not isinstance(search_payload, list):
        raise ApiError("Search payload must be a list")

    report_payload, timings["create_report"] = _timed(
        lambda: _request(
            method="POST",
            url=_api_url(args.base_url, f"/api/organizations/{organization_id}/reports"),
            timeout=args.request_timeout,
            headers=headers,
            json_payload={
                "title": f"Benchmark report {run_label}",
                "report_type": "readiness_report",
                "selected_document_ids": document_ids,
            },
        )
    )
    if not isinstance(report_payload, dict):
        raise ApiError("Report payload must be an object")
    report_id = str(report_payload["id"])

    _request(
        method="POST",
        url=_api_url(args.base_url, f"/api/reports/{report_id}/analyze"),
        timeout=args.request_timeout,
        headers=headers,
    )
    analyzed_payload, timings["analyze"] = _poll(
        lambda: _request(
            method="GET",
            url=_api_url(args.base_url, f"/api/reports/{report_id}"),
            timeout=args.request_timeout,
            headers=headers,
        ),
        timeout_seconds=args.pipeline_timeout,
        interval_seconds=args.poll_interval,
        is_ready=lambda payload: isinstance(payload, dict) and payload.get("status") != "analyzing",
    )
    if not isinstance(analyzed_payload, dict):
        raise ApiError("Analyzed report payload must be an object")

    requirements_payload, timings["fetch_requirements"] = _timed(
        lambda: _request(
            method="GET",
            url=_api_url(args.base_url, f"/api/organizations/{organization_id}/requirements"),
            timeout=args.request_timeout,
            headers=headers,
        )
    )
    matrix_payload, timings["fetch_matrix"] = _timed(
        lambda: _request(
            method="GET",
            url=_api_url(args.base_url, f"/api/reports/{report_id}/matrix"),
            timeout=args.request_timeout,
            headers=headers,
        )
    )
    if not isinstance(requirements_payload, list) or not isinstance(matrix_payload, list):
        raise ApiError("Requirements and matrix payloads must be lists")

    _request(
        method="POST",
        url=_api_url(args.base_url, f"/api/reports/{report_id}/generate"),
        timeout=args.request_timeout,
        headers=headers,
    )
    sections_payload, timings["generate"] = _poll(
        lambda: _request(
            method="GET",
            url=_api_url(args.base_url, f"/api/reports/{report_id}/sections"),
            timeout=args.request_timeout,
            headers=headers,
        ),
        timeout_seconds=args.pipeline_timeout,
        interval_seconds=args.poll_interval,
        is_ready=lambda payload: isinstance(payload, list) and len(payload) >= args.expected_section_count,
    )
    if not isinstance(sections_payload, list):
        raise ApiError("Sections payload must be a list")

    export_counts: dict[str, str] = {}
    for export_kind in ("docx", "matrix", "package", "explanations"):
        export_payload, timings[f"export_{export_kind}"] = _timed(
            lambda export_kind=export_kind: _request(
                method="POST",
                url=_api_url(args.base_url, f"/api/reports/{report_id}/export/{quote(export_kind)}"),
                timeout=args.request_timeout,
                headers=headers,
            )
        )
        if not isinstance(export_payload, dict):
            raise ApiError("Export payload must be an object")
        export_counts[export_kind] = str(export_payload["status"])

    return {
        "run_index": run_index,
        "organization_id": organization_id,
        "report_id": report_id,
        "document_ids": document_ids,
        "document_statuses": document_statuses,
        "report_status_after_analyze": str(analyzed_payload["status"]),
        "readiness_percent_after_analyze": analyzed_payload.get("readiness_percent"),
        "search_results_count": len(search_payload),
        "requirements_count": len(requirements_payload),
        "matrix_rows_count": len(matrix_payload),
        "sections_count": len(sections_payload),
        "export_statuses": export_counts,
        "timings_seconds": timings,
        "run_wall_time_seconds": round(time.perf_counter() - run_started, 4),
    }


def _collect_runs(args: argparse.Namespace) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    effective_concurrency = max(1, min(args.concurrency, args.runs))
    if effective_concurrency == 1 or args.runs == 1:
        runs: list[dict[str, object]] = []
        errors: list[dict[str, object]] = []
        for run_index in range(1, args.runs + 1):
            try:
                runs.append(_run_single_benchmark_run(args, run_index))
            except Exception as exc:
                errors.append({"run_index": run_index, "error": str(exc)})
        return runs, errors

    runs = []
    errors = []
    with ThreadPoolExecutor(max_workers=effective_concurrency) as executor:
        future_map = {}
        for run_index in range(1, args.runs + 1):
            future_map[executor.submit(_run_single_benchmark_run, args, run_index)] = run_index
            if args.stagger_seconds > 0 and run_index < args.runs:
                time.sleep(args.stagger_seconds)

        for future in as_completed(future_map):
            run_index = future_map[future]
            try:
                runs.append(future.result())
            except Exception as exc:
                errors.append({"run_index": run_index, "error": str(exc)})
    runs.sort(key=lambda item: int(item["run_index"]))
    errors.sort(key=lambda item: int(item["run_index"]))
    return runs, errors


def run_benchmark(args: argparse.Namespace) -> dict[str, object]:
    started = time.perf_counter()
    ai_status = _request(method="GET", url=_api_url(args.base_url, "/api/system/ai-status"), timeout=args.request_timeout)
    resource_sampler: DockerResourceSampler | None = None
    resource_profile: dict[str, object] | None = None

    if args.resource_profile == "docker":
        resource_sampler = DockerResourceSampler(
            compose_file=args.compose_file,
            services=[service.strip() for service in args.resource_services.split(",") if service.strip()],
            interval_seconds=args.resource_interval,
        )
        resource_sampler.start()

    try:
        runs, errors = _collect_runs(args)
    finally:
        if resource_sampler is not None:
            resource_sampler.stop()
            resource_profile = resource_sampler.to_payload(include_samples=args.include_resource_samples)

    total_wall_time_seconds = round(time.perf_counter() - started, 4)
    completed_runs = len(runs)
    failed_runs = len(errors)
    effective_concurrency = max(1, min(args.concurrency, args.runs))

    payload = {
        "captured_at": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
        "requested_runs": args.runs,
        "completed_runs": completed_runs,
        "failed_runs": failed_runs,
        "concurrency": effective_concurrency,
        "total_wall_time_seconds": total_wall_time_seconds,
        "throughput_runs_per_minute": throughput_per_minute(completed_runs, total_wall_time_seconds),
        "success_rate": success_rate(completed_runs, args.runs),
        "runs": runs,
        "summary": flatten_timing_metrics(runs),
        "ai_status": ai_status,
        "samples": [filename for filename, _category in SAMPLE_DOCUMENTS],
        "query": args.query,
        "expected_section_count": args.expected_section_count,
    }
    if resource_profile is not None:
        payload["resource_profile"] = resource_profile
    if errors:
        payload["errors"] = errors
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a live benchmark against the XAI Report Builder API.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email", default="admin@example.com")
    parser.add_argument("--password", default="ChangeMe123!")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--stagger-seconds", type=float, default=0.0)
    parser.add_argument("--query", default="лицензия локальные акты")
    parser.add_argument("--expected-section-count", type=int, default=9)
    parser.add_argument("--request-timeout", type=float, default=60.0)
    parser.add_argument("--pipeline-timeout", type=float, default=240.0)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--resource-profile", choices=("none", "docker"), default="none")
    parser.add_argument("--compose-file", type=Path, default=PROJECT_ROOT / "infra" / "docker-compose.yml")
    parser.add_argument("--resource-services", default="backend,worker,postgres,redis,ollama")
    parser.add_argument("--resource-interval", type=float, default=1.0)
    parser.add_argument("--include-resource-samples", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = run_benchmark(args)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 1 if payload.get("failed_runs", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
