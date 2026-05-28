from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from pathlib import Path

def resolve_repo_root() -> Path:
    candidates = [
        Path(__file__).resolve().parents[2],
        Path.cwd(),
    ]
    for candidate in candidates:
        if (candidate / "samples").exists() and (candidate / "backend").exists():
            return candidate
    raise RuntimeError("Could not resolve repository root.")


ROOT = resolve_repo_root()
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models import DocumentCategory, MemberRole, MemberStatus, Organization, OrganizationMember, User
from app.services.documents import create_document, process_document

MANIFEST_PATH = ROOT / "samples" / "demo_organizations" / "manifest.json"
GENERATED_DIR = ROOT / "samples" / "demo_organizations" / "generated"
ORGANIZATION_FIELDS = {
    "name",
    "short_name",
    "inn",
    "kpp",
    "ogrn",
    "legal_address",
    "actual_address",
    "organization_type",
    "okved",
    "website",
    "email",
    "phone",
    "director_name",
    "responsible_person",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import generated demo organizations into the current XAI Report Builder database.")
    parser.add_argument("--user-email", required=True, help="Email of an existing user who should receive org_admin access.")
    parser.add_argument("--skip-processing", action="store_true", help="Only create organizations and upload files without document processing.")
    return parser.parse_args()


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def ensure_membership(session, organization_id: str, user_id: str) -> None:
    membership = session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
    )
    if membership is not None:
        return
    session.add(
        OrganizationMember(
            organization_id=organization_id,
            user_id=user_id,
            role=MemberRole.org_admin,
            status=MemberStatus.active,
        )
    )
    session.commit()


def import_demo_pack(user_email: str, *, skip_processing: bool) -> None:
    manifest = load_manifest()
    session_factory = get_session_factory()
    created_orgs = 0
    created_docs = 0

    with session_factory() as session:
        user = session.scalar(select(User).where(User.email == user_email.lower()))
        if user is None:
            raise SystemExit(f"User not found: {user_email}")

        for item in manifest["organizations"]:
            existing = session.scalar(
                select(Organization).where(
                    Organization.name == item["name"],
                    Organization.website == item["website"],
                )
            )
            if existing is not None:
                ensure_membership(session, existing.id, user.id)
                print(f"Skip existing organization: {item['name']}")
                continue

            seed_manifest_path = GENERATED_DIR / item["slug"] / "seed_manifest.json"
            if not seed_manifest_path.exists():
                raise SystemExit(f"Missing generated seed manifest: {seed_manifest_path}")

            seed_manifest = json.loads(seed_manifest_path.read_text(encoding="utf-8"))
            profile_payload = dict(seed_manifest["organization"])
            profile_json = profile_payload.pop("profile_json", {})
            unknown_fields = {key: profile_payload.pop(key) for key in list(profile_payload) if key not in ORGANIZATION_FIELDS}
            if unknown_fields:
                profile_json.update(unknown_fields)
            organization = Organization(**profile_payload, profile_json=profile_json)
            session.add(organization)
            session.commit()
            session.refresh(organization)
            ensure_membership(session, organization.id, user.id)
            created_orgs += 1

            for file_meta in seed_manifest["files"]:
                file_path = GENERATED_DIR / item["slug"] / file_meta["file_name"]
                content = file_path.read_bytes()
                document = create_document(
                    session,
                    organization_id=organization.id,
                    uploaded_by_id=user.id,
                    file_name=file_meta["file_name"],
                    content=content,
                    content_type=mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
                    category=DocumentCategory(file_meta["category"]),
                    tags=file_meta["tags"],
                )
                created_docs += 1
                if not skip_processing:
                    process_document(session, document.id)

            print(f"Imported organization: {organization.name}")

    print(f"Done. Created organizations: {created_orgs}. Uploaded documents: {created_docs}.")


if __name__ == "__main__":
    args = parse_args()
    import_demo_pack(args.user_email, skip_processing=args.skip_processing)
