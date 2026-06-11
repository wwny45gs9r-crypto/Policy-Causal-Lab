import json
from sqlalchemy.orm import Session
from ..models import AuditLog


def log_event(db: Session, project_id: int, step: str, action: str, input_summary="", output_summary="", reasoning=None, warnings=None, user_action=""):
    entry = AuditLog(
        project_id=project_id, step=step, action=action,
        input_summary=input_summary, output_summary=output_summary,
        reasoning_summary_json=json.dumps(reasoning or {}, ensure_ascii=False),
        warnings_json=json.dumps(warnings or [], ensure_ascii=False),
        user_action=user_action,
    )
    db.add(entry)
    db.commit()
    return entry
