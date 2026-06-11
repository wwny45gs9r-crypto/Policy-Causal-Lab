from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Project
from ..schemas import ProjectCreate, ProjectOut
from .helpers import require_project

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(**payload.model_dump())
    db.add(project); db.commit(); db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.updated_at.desc()).all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    return require_project(db, project_id)


@router.post("/{project_id}/abort", response_model=ProjectOut)
def abort_project(project_id: int, db: Session = Depends(get_db)):
    project = require_project(db, project_id)
    project.status = "aborted"
    db.commit(); db.refresh(project)
    return project
