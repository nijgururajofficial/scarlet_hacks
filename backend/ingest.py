from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import faiss
import fitz
import numpy as np
from openai import OpenAI

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt"}
UPLOAD_PREFIX_PATTERN = re.compile(r"^[0-9a-f]{32}_(.+)$")


@dataclass(slots=True)
class SourceChunk:
    source_path: str
    source_name: str
    chunk_id: str
    chunk_text: str
    chunk_index: int
    modified_at_iso: str
    freshness_tag: str


@dataclass(slots=True)
class SearchResult:
    chunk: SourceChunk
    score: float


class IngestedKnowledgeBase:
    def __init__(self, chunks: list[SourceChunk], index: faiss.IndexFlatIP) -> None:
        self.chunks = chunks
        self.index = index

    def retrieve(
        self,
        query: str,
        client: OpenAI,
        top_k: int = 5,
        embedding_model: str = "text-embedding-3-small",
    ) -> list[SearchResult]:
        if not query.strip():
            return []

        embedding_response = client.embeddings.create(
            model=embedding_model,
            input=query,
        )

        query_vector = np.asarray(
            embedding_response.data[0].embedding,
            dtype="float32",
        ).reshape(1, -1)
        faiss.normalize_L2(query_vector)

        search_size = min(top_k, len(self.chunks))
        scores, indexes = self.index.search(query_vector, search_size)

        results: list[SearchResult] = []
        for score, chunk_position in zip(scores[0], indexes[0]):
            if chunk_position < 0:
                continue

            results.append(
                SearchResult(
                    chunk=self.chunks[chunk_position],
                    score=float(score),
                )
            )

        return results

    def select_brief_chunks(
        self,
        max_chunks_per_doc: int = 2,
        max_total_chunks: int = 12,
    ) -> list[SourceChunk]:
        selected_chunks: list[SourceChunk] = []
        chunk_counts: dict[str, int] = {}

        for chunk in self.chunks:
            current_count = chunk_counts.get(chunk.source_path, 0)
            if current_count >= max_chunks_per_doc:
                continue

            selected_chunks.append(chunk)
            chunk_counts[chunk.source_path] = current_count + 1

            if len(selected_chunks) >= max_total_chunks:
                break

        return selected_chunks


def collect_document_paths(paths: Sequence[str | Path]) -> list[Path]:
    document_paths: list[Path] = []

    for raw_path in paths:
        path_obj = Path(raw_path).expanduser().resolve()
        if not path_obj.exists():
            continue

        if path_obj.is_file() and path_obj.suffix.lower() in SUPPORTED_EXTENSIONS:
            document_paths.append(path_obj)
            continue

        if path_obj.is_dir():
            for nested_path in path_obj.rglob("*"):
                if nested_path.is_file() and nested_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    document_paths.append(nested_path.resolve())

    return list(dict.fromkeys(document_paths))


def extract_text_from_file(file_path: str | Path) -> str:
    path_obj = Path(file_path).expanduser().resolve()
    suffix = path_obj.suffix.lower()

    if suffix == ".pdf":
        pdf_document = fitz.open(path_obj)
        try:
            page_texts = [page.get_text() for page in pdf_document]
            return "\n\n".join(page_texts).strip()
        finally:
            pdf_document.close()

    return path_obj.read_text(encoding="utf-8").strip()


def chunk_text(text: str, chunk_size: int = 1200, chunk_overlap: int = 200) -> list[str]:
    normalized_text = text.replace("\r\n", "\n").strip()
    if not normalized_text:
        return []

    chunks: list[str] = []
    start_index = 0
    text_length = len(normalized_text)

    while start_index < text_length:
        end_index = min(start_index + chunk_size, text_length)

        if end_index < text_length:
            window_text = normalized_text[start_index:end_index]
            split_offset = max(
                window_text.rfind("\n\n"),
                window_text.rfind("\n"),
                window_text.rfind(". "),
            )
            if split_offset > chunk_size // 2:
                end_index = start_index + split_offset + 1

        chunk = normalized_text[start_index:end_index].strip()
        if chunk:
            chunks.append(chunk)

        if end_index >= text_length:
            break

        start_index = max(end_index - chunk_overlap, start_index + 1)

    return chunks


def build_knowledge_base(
    paths: Sequence[str | Path],
    client: OpenAI,
    embedding_model: str = "text-embedding-3-small",
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
    embedding_batch_size: int = 64,
) -> IngestedKnowledgeBase:
    document_paths = collect_document_paths(paths)
    if not document_paths:
        raise ValueError("No supported documents found. Expected .pdf, .md, or .txt files.")

    chunks: list[SourceChunk] = []
    embedding_inputs: list[str] = []

    for path_obj in document_paths:
        document_text = extract_text_from_file(path_obj)
        if not document_text:
            continue

        document_chunks = chunk_text(
            text=document_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        if not document_chunks:
            continue

        modified_at = datetime.fromtimestamp(path_obj.stat().st_mtime, tz=timezone.utc)
        modified_at_iso = modified_at.isoformat()
        freshness_tag = _build_freshness_tag(modified_at)

        for chunk_index, chunk in enumerate(document_chunks):
            chunk_id = f"{path_obj.stem}-{chunk_index}"
            chunks.append(
                SourceChunk(
                    source_path=str(path_obj),
                    source_name=_display_source_name(path_obj.name),
                    chunk_id=chunk_id,
                    chunk_text=chunk,
                    chunk_index=chunk_index,
                    modified_at_iso=modified_at_iso,
                    freshness_tag=freshness_tag,
                )
            )
            embedding_inputs.append(chunk)

    if not chunks:
        raise ValueError("Documents were found, but none produced usable text chunks.")

    embedding_rows: list[list[float]] = []
    for start_index in range(0, len(embedding_inputs), embedding_batch_size):
        batch_inputs = embedding_inputs[start_index : start_index + embedding_batch_size]
        embedding_response = client.embeddings.create(
            model=embedding_model,
            input=batch_inputs,
        )
        for item in embedding_response.data:
            embedding_rows.append(item.embedding)

    embedding_matrix = np.asarray(embedding_rows, dtype="float32")
    faiss.normalize_L2(embedding_matrix)

    index = faiss.IndexFlatIP(embedding_matrix.shape[1])
    index.add(embedding_matrix)
    return IngestedKnowledgeBase(chunks=chunks, index=index)


def _build_freshness_tag(modified_at: datetime) -> str:
    age_in_days = (datetime.now(tz=timezone.utc) - modified_at).days
    if age_in_days <= 30:
        return "fresh"
    if age_in_days <= 180:
        return "recent"
    return "stale"


def _display_source_name(file_name: str) -> str:
    pattern_match = UPLOAD_PREFIX_PATTERN.match(file_name)
    if pattern_match:
        return pattern_match.group(1)
    return file_name
