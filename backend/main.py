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

# This loads local environment variables early so API credentials are available during startup.
load_dotenv()

# This prefers package-relative imports when the backend is started with `uvicorn backend.main:app`.
try:
    # This imports the agent facade through the package so route handlers can call backend logic cleanly.
    from .agents import KnowledgeAgents
    # This imports the document collector so startup can discover demo docs from the shared folder.
    from .ingest import SUPPORTED_EXTENSIONS, collect_document_paths
except ImportError:
    # This falls back to local imports so the file can also run directly from the backend folder.
    from agents import KnowledgeAgents
    # This falls back to the local ingestion helpers for the same standalone execution path.
    from ingest import SUPPORTED_EXTENSIONS, collect_document_paths

# This points to the shared demo docs folder so startup can preload example company documents.
DEMO_DOCS_DIR = Path(__file__).resolve().parent.parent / "demo_docs"


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # This initializes runtime state before the API starts accepting requests.
    _initialize_app_state(app_instance)

    try:
        # This yields control back to FastAPI so the application can serve requests normally.
        yield
    finally:
        # This cleans up temporary upload files after the server stops.
        _cleanup_upload_dir(app_instance)

# This creates the FastAPI application that owns all backend and AI routes.
app = FastAPI(
    title="day 1 brain backend",
    version="1.0.0",
    lifespan=lifespan,
)

# This allows the local Streamlit frontend to call the backend during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BriefRequest(BaseModel):
    # This stores the selected role so Agent 1 can build the right onboarding brief.
    role: str


class SearchRequest(BaseModel):
    # This stores the user's current role so Agent 2 can answer within role boundaries.
    role: str
    # This stores the chat question that should be answered from the knowledge base.
    question: str

@app.get("/health")
def health() -> dict[str, object]:
    # This reports whether the API process is alive and how much knowledge is currently loaded.
    return {
        "status": "ok",
        "docs_loaded": len(app.state.document_paths),
        "chunks_loaded": app.state.chunk_count,
        "has_knowledge_base": app.state.knowledge_agents is not None,
    }


@app.post("/ingest")
async def ingest_documents(files: list[UploadFile] = File(...)) -> dict[str, int]:
    # This rejects empty upload submissions because there is nothing to ingest.
    if not files:
        # This returns a clear client error so the frontend can prompt the user to choose files.
        raise HTTPException(status_code=400, detail="Upload at least one supported document.")

    # This stores the newly saved file paths so the knowledge base can be rebuilt from them.
    saved_paths: list[Path] = []

    # This walks each uploaded file so it can be validated and saved to the upload directory.
    for upload in files:
        # This guards against unnamed uploads because they cannot be saved reliably.
        if not upload.filename:
            # This skips invalid uploads without failing the entire batch.
            continue

        # This reads the file suffix once so supported-format validation stays consistent.
        suffix = Path(upload.filename).suffix.lower()

        # This enforces the same supported extensions as the ingestion layer.
        if suffix not in SUPPORTED_EXTENSIONS:
            # This tells the caller exactly why the upload was rejected.
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file '{upload.filename}'. Expected PDF, markdown, or text.",
            )

        # This prefixes the original name with a UUID so uploads never collide on disk.
        target_path = app.state.upload_dir / f"{uuid4().hex}_{Path(upload.filename).name}"

        # This opens the destination file so the uploaded bytes can be streamed to disk.
        with target_path.open("wb") as file_handle:
            # This reads the uploaded bytes from FastAPI's upload wrapper.
            file_bytes = await upload.read()
            # This writes the uploaded content to disk so the ingestion pipeline can parse it.
            file_handle.write(file_bytes)

        # This tracks the saved path so it can be included in the next rebuild.
        saved_paths.append(target_path)

    # This fails when no valid files survived validation so the frontend can retry cleanly.
    if not saved_paths:
        # This indicates that nothing usable was uploaded in the request.
        raise HTTPException(status_code=400, detail="No valid files were uploaded.")

    # This extends the in-memory document registry so uploaded docs persist for this process.
    app.state.document_paths.extend(str(path) for path in saved_paths)

    # This rebuilds the in-memory FAISS index so the new documents become searchable immediately.
    _rebuild_knowledge_base()

    # This returns the updated document and chunk totals for the frontend status message.
    return {
        "docs": len(app.state.document_paths),
        "chunks": app.state.chunk_count,
    }


@app.post("/brief")
def generate_brief(request: BriefRequest) -> dict[str, object]:
    # This stops the request early when no documents are available to ground the brief.
    if app.state.knowledge_agents is None:
        # This guides the frontend to ingest or preload docs before asking for a brief.
        raise HTTPException(status_code=400, detail="No documents loaded yet. Upload docs first.")

    try:
        # This runs Agent 1 so the selected role gets a proactive onboarding summary.
        role_brief = app.state.knowledge_agents.generate_role_brief(request.role)
    except ValueError as exc:
        # This converts role validation errors into a clean client-facing API response.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # This returns the structured brief fields exactly as the frontend expects to render them.
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
    # This stops the request early when no documents are available to ground an answer.
    if app.state.knowledge_agents is None:
        # This guides the frontend to ingest or preload docs before starting chat.
        raise HTTPException(status_code=400, detail="No documents loaded yet. Upload docs first.")

    try:
        # This runs Agent 2 so the user gets a role-aware answer grounded in the current docs.
        question_answer = app.state.knowledge_agents.answer_question(
            role=request.role,
            question=request.question,
        )
    except ValueError as exc:
        # This converts validation failures into a clean client-facing API response.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # This returns the answer plus source metadata so the Streamlit UI can show citations.
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
    # This skips preload work when the demo docs folder does not exist yet.
    if not DEMO_DOCS_DIR.exists():
        # This returns quietly because demo docs are optional during early development.
        return

    # This discovers supported demo files so the backend can preload a starter knowledge base.
    demo_document_paths = collect_document_paths([DEMO_DOCS_DIR])

    # This skips rebuild work when no supported demo docs are present.
    if not demo_document_paths:
        # This returns quietly because there is nothing to preload.
        return

    # This stores the discovered demo docs as the active document set.
    app.state.document_paths = [str(path) for path in demo_document_paths]

    # This builds the initial knowledge base so health checks can report a ready backend.
    _rebuild_knowledge_base()


def _rebuild_knowledge_base() -> None:
    # This clears the active state when the document list is empty so routes fail gracefully.
    if not app.state.document_paths:
        # This removes the active agents because there is no knowledge base to serve.
        app.state.knowledge_agents = None
        # This resets the chunk counter so health stays accurate.
        app.state.chunk_count = 0
        # This returns because there is nothing to ingest.
        return

    try:
        # This rebuilds the agent bundle from all currently tracked document paths.
        app.state.knowledge_agents = KnowledgeAgents.from_document_paths(
            document_paths=app.state.document_paths,
        )
    except Exception as exc:
        # This clears the active agents so the API never serves a half-built knowledge base.
        app.state.knowledge_agents = None
        # This resets chunk count because the rebuild did not succeed.
        app.state.chunk_count = 0
        # This surfaces startup or ingest failures as API errors with useful context.
        raise HTTPException(status_code=500, detail=f"Failed to build knowledge base: {exc}") from exc

    # This records the total chunk count so health and ingest responses can display it quickly.
    app.state.chunk_count = len(app.state.knowledge_agents.knowledge_base.chunks)

def _initialize_app_state(app_instance: FastAPI) -> None:
    # This creates a temporary upload directory so user-uploaded files can be ingested from disk.
    app_instance.state.upload_dir = Path(tempfile.mkdtemp(prefix="day1_brain_uploads_"))
    # This initializes the active document list so health checks can report backend state.
    app_instance.state.document_paths = []
    # This initializes the chunk counter before any documents are loaded.
    app_instance.state.chunk_count = 0
    # This initializes the knowledge agent bundle as empty until documents are available.
    app_instance.state.knowledge_agents = None

    # This attempts to preload demo docs so the app can work immediately if examples are present.
    _load_demo_docs()


def _cleanup_upload_dir(app_instance: FastAPI) -> None:
    # This reads the temporary upload directory once so cleanup can happen safely.
    upload_dir = getattr(app_instance.state, "upload_dir", None)

    # This removes the temp upload directory so local runs do not leak files over time.
    if upload_dir and Path(upload_dir).exists():
        # This deletes the directory tree because uploaded docs are only needed while the app runs.
        shutil.rmtree(upload_dir, ignore_errors=True)


if __name__ == "__main__":
    # This starts the local FastAPI server when the file is run directly with `python main.py`.
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )
