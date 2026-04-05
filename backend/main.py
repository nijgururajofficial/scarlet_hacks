from __future__ import annotations

import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

load_dotenv()

try:
    from .agents import KnowledgeAgents
    from .ingest import SUPPORTED_EXTENSIONS, collect_document_paths
except ImportError:
    from agents import KnowledgeAgents
    from ingest import SUPPORTED_EXTENSIONS, collect_document_paths

DEMO_DOCS_DIR = Path(__file__).resolve().parent.parent / "demo_docs"


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    _initialize_app_state(app_instance)

    try:
        yield
    finally:
        _cleanup_upload_dir(app_instance)

app = FastAPI(
    title="day 1 brain backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BriefRequest(BaseModel):
    role: str


class SearchRequest(BaseModel):
    role: str
    question: str


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "docs_loaded": len(app.state.document_paths),
        "chunks_loaded": app.state.chunk_count,
        "has_knowledge_base": app.state.knowledge_agents is not None,
    }


@app.post("/ingest")
async def ingest_documents(files: list[UploadFile] = File(...)) -> dict[str, int]:
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one supported document.")

    saved_paths: list[Path] = []

    for upload in files:
        if not upload.filename:
            continue

        suffix = Path(upload.filename).suffix.lower()

        if suffix not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file '{upload.filename}'. Expected PDF, markdown, or text.",
            )

        target_path = app.state.upload_dir / f"{uuid4().hex}_{Path(upload.filename).name}"

        with target_path.open("wb") as file_handle:
            file_bytes = await upload.read()
            file_handle.write(file_bytes)

        saved_paths.append(target_path)

    if not saved_paths:
        raise HTTPException(status_code=400, detail="No valid files were uploaded.")

    app.state.document_paths.extend(str(path) for path in saved_paths)
    _rebuild_knowledge_base()

    return {
        "docs": len(app.state.document_paths),
        "chunks": app.state.chunk_count,
    }


@app.post("/brief")
def generate_brief(request: BriefRequest) -> dict[str, object]:
    if app.state.knowledge_agents is None:
        raise HTTPException(status_code=400, detail="No documents loaded yet. Upload docs first.")

    try:
        role_brief = app.state.knowledge_agents.generate_role_brief(request.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "role": role_brief.role,
        "must_knows": role_brief.must_knows,
        "tools": role_brief.tools_checklist,
        "contacts": role_brief.key_contacts,
        "roadmap": role_brief.roadmap,
        "sources": role_brief.source_docs,
    }


@app.post("/search")
def search_knowledge(request: SearchRequest) -> dict[str, object]:
    if app.state.knowledge_agents is None:
        raise HTTPException(status_code=400, detail="No documents loaded yet. Upload docs first.")

    try:
        question_answer = app.state.knowledge_agents.answer_question(
            role=request.role,
            question=request.question,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "answer": question_answer.answer,
        "action": question_answer.action,
        "who_to_contact": question_answer.who_to_contact,
        "risk_level": question_answer.risk_level,
        "next_steps": question_answer.next_steps,
        "sources": question_answer.source_docs,
        "freshness": question_answer.freshness,
    }


def _load_demo_docs() -> None:
    if not DEMO_DOCS_DIR.exists():
        return

    demo_document_paths = collect_document_paths([DEMO_DOCS_DIR])

    if not demo_document_paths:
        return

    app.state.document_paths = [str(path) for path in demo_document_paths]
    _rebuild_knowledge_base()


def _rebuild_knowledge_base() -> None:
    if not app.state.document_paths:
        app.state.knowledge_agents = None
        app.state.chunk_count = 0
        return

    try:
        app.state.knowledge_agents = KnowledgeAgents.from_document_paths(
            document_paths=app.state.document_paths,
        )
    except Exception as exc:
        app.state.knowledge_agents = None
        app.state.chunk_count = 0
        raise HTTPException(status_code=500, detail=f"Failed to build knowledge base: {exc}") from exc

    app.state.chunk_count = len(app.state.knowledge_agents.knowledge_base.chunks)


def _initialize_app_state(app_instance: FastAPI) -> None:
    app_instance.state.upload_dir = Path(tempfile.mkdtemp(prefix="day1_brain_uploads_"))
    app_instance.state.document_paths = []
    app_instance.state.chunk_count = 0
    app_instance.state.knowledge_agents = None
    _load_demo_docs()


def _cleanup_upload_dir(app_instance: FastAPI) -> None:
    upload_dir = getattr(app_instance.state, "upload_dir", None)

    if upload_dir and Path(upload_dir).exists():
        shutil.rmtree(upload_dir, ignore_errors=True)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )
