from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .config import settings
from .database import Base, engine
from .routers import admin, analysis, causal_workflow, chat, data, files, logs, methods, projects, reports, research_briefs, tasks

Base.metadata.create_all(bind=engine)
settings.storage_path.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="Policy Causal Lab API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
for router in [projects.router, files.router, chat.router, data.router, methods.router, analysis.router, causal_workflow.router, reports.router, logs.router, research_briefs.router, tasks.router, admin.router]:
    app.include_router(router)
app.mount("/storage", StaticFiles(directory=str(settings.storage_path)), name="storage")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "policy-causal-lab-api"}


@app.get("/health")
def root_health():
    return health()


@app.get("/api/hello")
def hello():
    return {"message": "hello"}
