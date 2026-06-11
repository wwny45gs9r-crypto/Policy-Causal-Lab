import json
import pandas as pd
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .. import models
from ..config import settings
from ..services.data_profiler import read_dataset


def require_project(db: Session, project_id: int):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    return project


def latest(db: Session, model, project_id: int):
    return db.query(model).filter(model.project_id == project_id).order_by(model.id.desc()).first()


def data_file(db: Session, project_id: int):
    files = db.query(models.UploadedFile).filter(models.UploadedFile.project_id == project_id, models.UploadedFile.file_type == "data").order_by(models.UploadedFile.id.desc()).all()
    if not files:
        raise HTTPException(400, "请先上传数据文件")
    return files[0]


def data_files(db: Session, project_id: int):
    files = db.query(models.UploadedFile).filter(models.UploadedFile.project_id == project_id, models.UploadedFile.file_type == "data").order_by(models.UploadedFile.id.asc()).all()
    if not files:
        raise HTTPException(400, "请先上传数据文件")
    return files


def load_data(db: Session, project_id: int):
    try:
        clean_path = settings.storage_path / str(project_id) / "clean_data_v1.csv"
        if clean_path.exists():
            return read_dataset(str(clean_path))
        frames = []
        for item in data_files(db, project_id):
            frame = read_dataset(item.file_path)
            frame["_source_file"] = item.filename
            frames.append(frame)
        return pd.concat(frames, ignore_index=True, sort=False)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


def parse(value: str):
    return json.loads(value)
