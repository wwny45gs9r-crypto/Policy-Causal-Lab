from datetime import datetime
import json
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import PromptTemplate, SystemAuditLog, SystemKnowledgeChunk, SystemKnowledgeSource
from ..schemas import KnowledgeSearchRequest, ModelConfigRequest, PromptSaveRequest, SystemKnowledgeSourceRequest
from ..services.document_parser import extract_text
from ..services.gitee_fetcher import sync_repo
from ..services.prompt_manager import MODULES, get_prompt, list_prompts
from ..services.system_knowledge_base import save_chunks, search_chunks

router = APIRouter(prefix="/api/admin", tags=["admin"])
DEFAULT_REPO = "https://gitee.com/zhiyuanryanchen/causal-inference-machine-learning"


def require_admin(x_user_role: str = Header("user")):
    if x_user_role != "admin":
        raise HTTPException(403, "需要管理员权限")
    return x_user_role


def source_out(row):
    return {"id": row.id, "repo_url": row.repo_url, "branch": row.branch, "status": row.status, "last_synced_at": row.last_synced_at}


def log_system(db: Session, action: str, input_summary="", output_summary="", warnings=None):
    db.add(SystemAuditLog(action=action, input_summary=input_summary, output_summary=output_summary, warnings_json=json.dumps(warnings or [], ensure_ascii=False)))
    db.commit()


@router.get("/knowledge-sources", dependencies=[Depends(require_admin)])
def list_sources(db: Session = Depends(get_db)):
    rows = db.query(SystemKnowledgeSource).all()
    return {"default_repo_url": DEFAULT_REPO, "sources": [source_out(row) for row in rows]}


@router.post("/knowledge-sources", dependencies=[Depends(require_admin)])
def add_source(payload: SystemKnowledgeSourceRequest, db: Session = Depends(get_db)):
    row = SystemKnowledgeSource(repo_url=payload.repo_url, branch=payload.branch)
    db.add(row); db.commit(); db.refresh(row); log_system(db, "create_knowledge_source", input_summary=payload.repo_url)
    return source_out(row)


@router.post("/knowledge-sources/{source_id}/sync", dependencies=[Depends(require_admin)])
def sync_source(source_id: int, db: Session = Depends(get_db)):
    source = db.get(SystemKnowledgeSource, source_id)
    if not source: raise HTTPException(404, "系统知识源不存在")
    target = settings.storage_path.parent / "system_knowledge" / str(source.id)
    try:
        files = sync_repo(source.repo_url, source.branch, target)
        db.query(SystemKnowledgeChunk).filter(SystemKnowledgeChunk.source_id == source.id).delete(); db.commit()
        chunks, parsed = 0, 0
        for file in files:
            try:
                chunks += save_chunks(db, source.id, str(file.relative_to(target)), extract_text(str(file))); parsed += 1
            except Exception:
                continue
        source.status = "success"; source.last_synced_at = datetime.utcnow(); db.commit()
        result = {"status": source.status, "parsed_files": parsed, "chunks": chunks}
        log_system(db, "sync_knowledge_source", input_summary=source.repo_url, output_summary=json.dumps(result))
        return result
    except Exception as exc:
        source.status = "failed"; db.commit()
        log_system(db, "sync_knowledge_source_failed", input_summary=source.repo_url, warnings=[str(exc)])
        raise HTTPException(400, f"系统知识库同步失败: {exc}")


@router.get("/knowledge-chunks", dependencies=[Depends(require_admin)])
def chunks(q: str = Query(""), top_k: int = Query(20), db: Session = Depends(get_db)):
    if q: return {"chunks": search_chunks(db, q, top_k, include_content=True)}
    rows = db.query(SystemKnowledgeChunk).limit(top_k)
    return {"chunks": [{"id": row.id, "source_id": row.source_id, "file_path": row.file_path, "chunk_index": row.chunk_index, "content": row.content} for row in rows]}


@router.post("/knowledge-search", dependencies=[Depends(require_admin)])
def search(payload: KnowledgeSearchRequest, db: Session = Depends(get_db)):
    return {"chunks": search_chunks(db, payload.query, payload.top_k, include_content=True)}


@router.get("/prompts", dependencies=[Depends(require_admin)])
def prompts(db: Session = Depends(get_db)): return list_prompts(db)


@router.get("/prompts/{module_name}", dependencies=[Depends(require_admin)])
def prompt(module_name: str, db: Session = Depends(get_db)):
    try: return get_prompt(db, module_name)
    except ValueError as exc: raise HTTPException(404, str(exc))


@router.post("/prompts/{module_name}", dependencies=[Depends(require_admin)])
def save_prompt(module_name: str, payload: PromptSaveRequest, db: Session = Depends(get_db)):
    if module_name not in MODULES: raise HTTPException(404, "未知 Prompt 模块")
    latest = db.query(PromptTemplate).filter(PromptTemplate.scope == "system", PromptTemplate.project_id.is_(None), PromptTemplate.module_name == module_name).order_by(PromptTemplate.version.desc()).first()
    row = PromptTemplate(scope="system", module_name=module_name, system_prompt=payload.system_prompt, output_format=payload.output_format, version=(latest.version + 1 if latest else 1), is_default=True)
    db.add(row); db.commit(); db.refresh(row); log_system(db, "save_system_prompt", input_summary=f"{module_name} v{row.version}: {payload.change_note}", output_summary=payload.output_format)
    return get_prompt(db, module_name)


@router.get("/model-config", dependencies=[Depends(require_admin)])
def model_config():
    return {"deepseek_model": settings.DEEPSEEK_MODEL, "deepseek_base_url": settings.DEEPSEEK_BASE_URL, "api_key_configured": bool(settings.DEEPSEEK_API_KEY), "api_key_exposed": False}


@router.post("/model-config", dependencies=[Depends(require_admin)])
def update_model_config(payload: ModelConfigRequest, db: Session = Depends(get_db)):
    allowed = {"deepseek-v4-pro", "deepseek-v4-flash"}
    if payload.deepseek_model not in allowed: raise HTTPException(400, "仅允许 deepseek-v4-pro 或 deepseek-v4-flash")
    settings.DEEPSEEK_MODEL = payload.deepseek_model
    log_system(db, "update_model_config", input_summary=payload.deepseek_model)
    return model_config()


@router.get("/audit-logs", dependencies=[Depends(require_admin)])
def audit_logs(db: Session = Depends(get_db)):
    rows = db.query(SystemAuditLog).order_by(SystemAuditLog.id.desc()).limit(200)
    return [{"id": row.id, "action": row.action, "input_summary": row.input_summary, "output_summary": row.output_summary, "warnings": json.loads(row.warnings_json), "created_at": row.created_at} for row in rows]
