from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings


class FileStorage:
    def __init__(self) -> None:
        self.root = Path(get_settings().storage_path).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def document_dir(self, organization_id: str) -> Path:
        path = self.root / organization_id / "documents"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def export_dir(self, organization_id: str) -> Path:
        path = self.root / organization_id / "exports"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_document_bytes(self, organization_id: str, file_name: str, content: bytes) -> str:
        target = self.document_dir(organization_id) / f"{uuid4().hex[:12]}_{Path(file_name).name}"
        target.write_bytes(content)
        return str(target)

    def create_export_path(self, organization_id: str, file_name: str) -> str:
        target = self.export_dir(organization_id) / f"{uuid4().hex[:12]}_{Path(file_name).name}"
        return str(target)

    def delete_file(self, path: str) -> None:
        file_path = Path(path)
        if file_path.exists():
            file_path.unlink()


storage = FileStorage()
