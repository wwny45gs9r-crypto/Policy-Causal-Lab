from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import UploadedFile
from ..schemas import PolicyTextRequest
from ..services.audit_logger import log_event
from ..services.policy_parser import parse_policy
from ..services.deepseek_client import DeepSeekClient
from ..services.storage_service import LocalStorageService
from .helpers import require_project

router = APIRouter(prefix="/api/projects", tags=["files"])


def save(project_id: int, file: UploadFile, kind: str, allowed: set[str], db: Session):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, f"不支持的文件类型: {suffix}")
    path = LocalStorageService().save_file(project_id, file, "uploads")
    record = UploadedFile(project_id=project_id, filename=file.filename or path.name, file_type=kind, file_path=str(path))
    db.add(record); db.commit()
    log_event(db, project_id, "file_upload", f"upload_{kind}", input_summary=record.filename, output_summary=str(path))
    return record


@router.post("/{project_id}/upload-policy")
def upload_policy(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    require_project(db, project_id)
    record = save(project_id, file, "policy", {".txt", ".md", ".pdf", ".docx"}, db)
    parsed = parse_policy(record.file_path)
    result = DeepSeekClient().complete_for_project(db, project_id, "policy_understanding", "请提取结构化政策理解结果", {"policy_text": parsed["policy_text"][:12000]})
    extracted_path = Path(record.file_path).with_suffix(".extracted.txt"); extracted_path.write_text(parsed["policy_text"], encoding="utf-8")
    refs = result.get("knowledge_refs", [])
    log_event(db, project_id, "policy_understanding", "parse", output_summary=str(result.get("content", ""))[:2000], reasoning={"used_system_knowledge": bool(refs), "knowledge_refs": refs}, warnings=[result["warning"]] if result.get("warning") else [])
    return {"file_id": record.id, "policy_summary": parsed["summary"], "policy_understanding": result.get("content", {}), "warnings": [result["warning"]] if result.get("warning") else []}


@router.post("/{project_id}/policy-text")
def policy_text(project_id: int, payload: PolicyTextRequest, db: Session = Depends(get_db)):
    require_project(db, project_id)
    text = payload.text.strip()
    if not text:
        raise HTTPException(400, "请填写政策资料文本")
    result = DeepSeekClient().complete_for_project(db, project_id, "policy_understanding", "请理解这段政策资料，并提取制度背景、政策对象、实施时间、潜在处理组和可能结果变量。", {"policy_text": text[:12000]})
    refs = result.get("knowledge_refs", [])
    log_event(db, project_id, "policy_understanding", "text", input_summary=text[:500], output_summary=str(result.get("content", ""))[:2000], reasoning={"used_system_knowledge": bool(refs), "knowledge_refs": refs}, warnings=[result["warning"]] if result.get("warning") else [])
    return {"message": result.get("content", ""), "warnings": [result["warning"]] if result.get("warning") else []}


@router.post("/{project_id}/upload-data")
def upload_data(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    require_project(db, project_id)
    record = save(project_id, file, "data", {".csv", ".xlsx", ".xls", ".dta"}, db)
    count = db.query(UploadedFile).filter(UploadedFile.project_id == project_id, UploadedFile.file_type == "data").count()
    return {"file_id": record.id, "filename": record.filename, "status": "uploaded", "data_file_count": count}
