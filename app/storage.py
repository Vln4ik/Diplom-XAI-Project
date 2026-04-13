from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _data_root() -> Path:
    root = Path(os.getenv("DIPLOM_DATA_DIR", "data")).resolve()
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "uploads").mkdir(parents=True, exist_ok=True)
    return root


def _report_path(report_id: str) -> Path:
    return _data_root() / "reports" / f"{report_id}.json"


def upload_dir(report_id: str) -> Path:
    path = _data_root() / "uploads" / report_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def create_report(title: str, profile_id: str) -> dict[str, Any]:
    report_id = f"rep-{uuid4().hex[:10]}"
    now = _utc_now()
    report = {
        "id": report_id,
        "title": title,
        "profile_id": profile_id,
        "status": "created",
        "created_at": now,
        "updated_at": now,
        "documents": [],
        "extracted_facts": [],
        "norm_references": [],
        "report_draft": None,
        "evidence_map": [],
        "validation_log": [],
        "audit_trace": [],
    }
    add_audit(report, "report_created", {"profile_id": profile_id})
    save_report(report)
    return report


def save_report(report: dict[str, Any]) -> None:
    report["updated_at"] = _utc_now()
    _write_json(_report_path(report["id"]), report)


def list_reports() -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    reports_dir = _data_root() / "reports"
    for path in sorted(reports_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        reports.append(
            {
                "id": payload["id"],
                "title": payload["title"],
                "profile_id": payload["profile_id"],
                "status": payload["status"],
                "updated_at": payload["updated_at"],
            }
        )
    reports.sort(key=lambda item: item["updated_at"], reverse=True)
    return reports


def get_report(report_id: str) -> dict[str, Any] | None:
    path = _report_path(report_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def add_audit(report: dict[str, Any], action: str, details: dict[str, Any] | None = None) -> None:
    report["audit_trace"].append(
        {
            "id": f"audit-{uuid4().hex[:10]}",
            "ts": _utc_now(),
            "action": action,
            "details": details or {},
        }
    )


def add_document(report: dict[str, Any], file_name: str, stored_path: str, mime_type: str | None, size_bytes: int) -> dict[str, Any]:
    doc = {
        "id": f"doc-{uuid4().hex[:10]}",
        "file_name": file_name,
        "stored_path": stored_path,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "uploaded_at": _utc_now(),
    }
    report["documents"].append(doc)
    add_audit(report, "document_uploaded", {"file_name": file_name, "size_bytes": size_bytes})
    return doc
