from pathlib import Path
import shutil
from fastapi import UploadFile
from ..config import settings


class LocalStorageService:
    def save_file(self, project_id: int, file: UploadFile, category: str) -> Path:
        root = settings.storage_path / str(project_id) / category
        root.mkdir(parents=True, exist_ok=True)
        path = root / (file.filename or "upload.bin")
        with path.open("wb") as target:
            shutil.copyfileobj(file.file, target)
        return path

    def get_file_path(self, project_id: int, filename: str, category: str) -> Path:
        return settings.storage_path / str(project_id) / category / filename

    def delete_file(self, path: Path):
        path.unlink(missing_ok=True)


class S3StorageService:
    """Deployment extension point for S3-compatible object storage."""


class MinIOStorageService:
    """Deployment extension point for MinIO object storage."""
