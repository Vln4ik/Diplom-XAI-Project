from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.schemas import (
    ChatMessageResponse,
    ChatModelInfo,
    ReportCreateRequest,
    ReportCreateResponse,
    ValidationRequest,
    ValidationResponse,
)
from app.services.chat_models import list_chat_models
from app.services.chat_orchestrator import ChatAttachment, process_chat_turn
from app.services.extraction import extract_facts
from app.services.generation import generate_report
from app.services.normative import build_norm_references
from app.services.profiles import get_profile, list_profiles
from app.storage import add_audit, add_document, create_report, get_report, list_reports, save_report, upload_dir

app = FastAPI(
    title="XAI Report Builder",
    description="MVP сервиса подготовки объяснимых отчетов для надзорных органов",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UI_FILE = Path(__file__).resolve().parent / "static" / "index.html"


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "xai-report-builder",
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ui", response_class=HTMLResponse)
def ui() -> HTMLResponse:
    if not UI_FILE.exists():
        raise HTTPException(status_code=500, detail="UI file is missing")
    return HTMLResponse(UI_FILE.read_text(encoding="utf-8"))


@app.get("/chat/models")
def chat_models() -> dict[str, list[ChatModelInfo]]:
    return {"models": [ChatModelInfo(**item) for item in list_chat_models()]}


@app.post("/chat/message", response_model=ChatMessageResponse)
async def chat_message(
    message: str = Form(default=""),
    profile_id: str = Form(default="rosobrnadzor"),
    model_id: str = Form(default="pipeline-basic"),
    report_id: str | None = Form(default=None),
    files: list[UploadFile] | None = File(default=None),
) -> ChatMessageResponse:
    attachments: list[ChatAttachment] = []
    for file in files or []:
        data = await file.read()
        if not data:
            continue
        attachments.append(
            ChatAttachment(
                file_name=Path(file.filename or "document.bin").name,
                content_type=file.content_type,
                data=data,
            )
        )

    try:
        result = process_chat_turn(
            message=message,
            profile_id=profile_id,
            model_id=model_id,
            report_id=report_id,
            attachments=attachments,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ChatMessageResponse(**result)


@app.get("/profiles")
def profiles() -> dict[str, list[dict[str, str]]]:
    return {"profiles": list_profiles()}


@app.get("/reports")
def reports() -> dict[str, list[dict[str, str]]]:
    return {"reports": list_reports()}


@app.post("/reports/create", response_model=ReportCreateResponse)
def report_create(payload: ReportCreateRequest) -> ReportCreateResponse:
    try:
        get_profile(payload.profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    report = create_report(title=payload.title, profile_id=payload.profile_id)
    return ReportCreateResponse(report_id=report["id"], status=report["status"])


@app.get("/reports/{report_id}")
def report_get(report_id: str) -> dict:
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.post("/reports/{report_id}/documents")
async def report_upload_documents(report_id: str, files: list[UploadFile] = File(...)) -> dict:
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    saved: list[dict] = []
    destination = upload_dir(report_id)

    for file in files:
        original_name = Path(file.filename or "document.bin").name
        data = await file.read()
        if not data:
            continue

        stored_name = f"{uuid4().hex[:8]}_{original_name}"
        stored_path = destination / stored_name
        stored_path.write_bytes(data)

        doc = add_document(
            report,
            file_name=original_name,
            stored_path=str(stored_path),
            mime_type=file.content_type,
            size_bytes=len(data),
        )
        saved.append(doc)

    if not saved:
        raise HTTPException(status_code=400, detail="No files were uploaded")

    report["status"] = "documents_uploaded"
    save_report(report)

    return {"report_id": report_id, "uploaded": saved}


@app.post("/reports/{report_id}/extract")
def report_extract(report_id: str) -> dict:
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    if not report["documents"]:
        raise HTTPException(status_code=400, detail="No documents uploaded")

    profile = get_profile(report["profile_id"])
    extracted = extract_facts(profile=profile, documents=report["documents"])

    report["extracted_facts"] = extracted["facts"]
    report["status"] = "facts_extracted"
    add_audit(
        report,
        "facts_extracted",
        {
            "required_filled": extracted["required_filled"],
            "required_total": extracted["required_total"],
            "score_complete": extracted["score_complete"],
        },
    )
    save_report(report)

    return {
        "report_id": report_id,
        "score_complete": extracted["score_complete"],
        "required_filled": extracted["required_filled"],
        "required_total": extracted["required_total"],
        "facts": extracted["facts"],
    }


@app.post("/reports/{report_id}/generate")
def report_generate(report_id: str, use_llm: bool | None = None) -> dict:
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    if not report["extracted_facts"]:
        raise HTTPException(status_code=400, detail="Run /reports/{report_id}/extract before generation")

    profile = get_profile(report["profile_id"])

    norm_references = build_norm_references(profile, report["extracted_facts"])
    generated = generate_report(profile, report["extracted_facts"], norm_references, use_llm=use_llm)

    report["norm_references"] = norm_references
    report["report_draft"] = generated["draft"]
    report["evidence_map"] = generated["evidence_map"]
    report["status"] = "draft_generated"

    add_audit(
        report,
        "report_generated",
        {
            "score_conf": generated["draft"]["overall_metrics"]["Score_conf"],
            "score_complete": generated["draft"]["overall_metrics"]["Score_complete"],
            "sections": len(generated["draft"]["sections"]),
        },
    )

    save_report(report)

    return {
        "report_id": report_id,
        "overall_metrics": generated["draft"]["overall_metrics"],
        "generation_meta": generated["draft"].get("generation_meta", {}),
        "sections": [
            {
                "section_id": section["section_id"],
                "title": section["title"],
                "status": section["status"],
                "metrics": section["metrics"],
            }
            for section in generated["draft"]["sections"]
        ],
    }


@app.get("/reports/{report_id}/draft")
def report_draft(report_id: str) -> dict:
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    if report["report_draft"] is None:
        raise HTTPException(status_code=400, detail="Draft is not generated")

    return {
        "report_id": report_id,
        "draft": report["report_draft"],
    }


@app.get("/reports/{report_id}/explain")
def report_explain(report_id: str) -> dict:
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    if not report["evidence_map"]:
        raise HTTPException(status_code=400, detail="Evidence map is empty. Run generation first")

    return {
        "report_id": report_id,
        "formula": "Score_conf = 0.4*S_source + 0.35*S_consistency + 0.25*S_norm",
        "evidence_map": report["evidence_map"],
    }


@app.post("/reports/{report_id}/validate", response_model=ValidationResponse)
def report_validate(report_id: str, payload: ValidationRequest) -> ValidationResponse:
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    draft = report.get("report_draft")
    if not draft:
        raise HTTPException(status_code=400, detail="Draft is not generated")

    sections = draft["sections"]
    section = next((item for item in sections if item["section_id"] == payload.section_id), None)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")

    section["validation_status"] = payload.decision
    if payload.decision == "approved":
        section["status"] = "ready"
    elif payload.decision == "rejected":
        section["status"] = "rejected"
    else:
        section["status"] = "requires_review"

    decision = {
        "id": f"val-{uuid4().hex[:10]}",
        "ts": datetime.now(timezone.utc).isoformat(),
        "section_id": payload.section_id,
        "decision": payload.decision,
        "reviewer": payload.reviewer,
        "comment": payload.comment,
    }
    report["validation_log"].append(decision)

    section_statuses = [item["validation_status"] for item in sections]
    if section_statuses and all(status == "approved" for status in section_statuses):
        report["status"] = "validated"
    elif any(status == "rejected" for status in section_statuses):
        report["status"] = "rejected"
    else:
        report["status"] = "under_review"

    add_audit(
        report,
        "validation_decision",
        {
            "section_id": payload.section_id,
            "decision": payload.decision,
            "reviewer": payload.reviewer,
        },
    )

    save_report(report)

    return ValidationResponse(
        report_id=report_id,
        section_id=payload.section_id,
        decision=payload.decision,
        status=report["status"],
    )
