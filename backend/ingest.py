from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import faiss
import fitz
import numpy as np
from openai import OpenAI

# This set defines which document formats the ingestion flow knows how to parse.
SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt"}


@dataclass(slots=True)
class SourceChunk:
    # This identifies the source file path so the UI can trace answers back to the original doc.
    source_path: str
    # This stores a cleaner display name so source tags look readable in the UI.
    source_name: str
    # This keeps a stable chunk identifier for downstream UI state or caching.
    chunk_id: str
    # This stores the actual chunk text that gets embedded and retrieved.
    chunk_text: str
    # This preserves chunk order within a document so debugging retrieval is easier.
    chunk_index: int
    # This stores the source file's modified timestamp in ISO format for display and logging.
    modified_at_iso: str
    # This gives the UI a simple freshness label without recalculating date math later.
    freshness_tag: str


@dataclass(slots=True)
class SearchResult:
    # This holds the matched chunk so callers can access source metadata and context text together.
    chunk: SourceChunk
    # This stores the FAISS similarity score so callers can sort or filter low-confidence matches.
    score: float


class IngestedKnowledgeBase:
    # This object keeps chunks and the FAISS index together so retrieval stays self-contained.
    def __init__(self, chunks: list[SourceChunk], index: faiss.IndexFlatIP) -> None:
        # This stores the original chunk metadata so search results can map back to source docs.
        self.chunks = chunks
        # This stores the normalized FAISS index used for cosine-similarity retrieval.
        self.index = index

    def retrieve(
        self,
        query: str,
        client: OpenAI,
        top_k: int = 5,
        embedding_model: str = "text-embedding-3-small",
    ) -> list[SearchResult]:
        # This skips empty questions so the embedding API is not called with invalid input.
        if not query.strip():
            # This returns no matches because there is nothing meaningful to retrieve against.
            return []

        # This embeds the query so it can be compared semantically against document chunks.
        embedding_response = client.embeddings.create(
            model=embedding_model,
            input=query,
        )

        # This converts the embedding into FAISS-friendly float32 values for fast vector math.
        query_vector = np.asarray(
            embedding_response.data[0].embedding,
            dtype="float32",
        ).reshape(1, -1)

        # This normalizes the query vector so inner product behaves like cosine similarity.
        faiss.normalize_L2(query_vector)

        # This limits search size to available chunks so FAISS does not return unnecessary blanks.
        search_size = min(top_k, len(self.chunks))

        # This runs semantic retrieval over the in-memory index to find the nearest chunks.
        scores, indexes = self.index.search(query_vector, search_size)

        # This accumulates rich results so callers receive both content and scores together.
        results: list[SearchResult] = []

        # This walks the returned positions so we can rebuild chunk objects in rank order.
        for score, chunk_position in zip(scores[0], indexes[0]):
            # This guards against FAISS placeholder values when no real hit exists.
            if chunk_position < 0:
                # This skips invalid positions because they do not map to a stored chunk.
                continue

            # This packages the matched chunk with its similarity score for downstream use.
            results.append(
                SearchResult(
                    chunk=self.chunks[chunk_position],
                    score=float(score),
                )
            )

        # This returns semantically ranked chunks for the answering agent to ground its reply.
        return results

    def select_brief_chunks(
        self,
        max_chunks_per_doc: int = 2,
        max_total_chunks: int = 12,
    ) -> list[SourceChunk]:
        # This keeps at least a couple chunks from each document so the brief sees broad coverage.
        selected_chunks: list[SourceChunk] = []
        # This tracks how many chunks each document has contributed so one file cannot dominate.
        chunk_counts: dict[str, int] = {}

        # This iterates in ingestion order so the brief sees early document sections first.
        for chunk in self.chunks:
            # This reads the current count so the next limit check stays concise.
            current_count = chunk_counts.get(chunk.source_path, 0)

            # This caps per-document contribution so context stays balanced across the knowledge base.
            if current_count >= max_chunks_per_doc:
                # This skips extra chunks from the same document after the quota is reached.
                continue

            # This adds the chunk to the brief context set because it still fits the quotas.
            selected_chunks.append(chunk)
            # This increments the per-document count so later chunks respect the cap.
            chunk_counts[chunk.source_path] = current_count + 1

            # This stops once the overall budget is full so prompts remain compact enough for the model.
            if len(selected_chunks) >= max_total_chunks:
                # This exits early because the brief already has enough broad context.
                break

        # This returns a doc-balanced slice of the knowledge base for proactive brief generation.
        return selected_chunks


def collect_document_paths(paths: Sequence[str | Path]) -> list[Path]:
    # This gathers supported files from mixed file and directory inputs.
    document_paths: list[Path] = []

    # This expands each user-provided input so a directory can contribute many files.
    for raw_path in paths:
        # This converts every input into a Path object so filesystem checks stay consistent.
        path_obj = Path(raw_path).expanduser().resolve()

        # This skips missing paths because they cannot contribute any knowledge.
        if not path_obj.exists():
            # This continues gracefully so one bad path does not block a full ingest run.
            continue

        # This handles a single document path without unnecessary recursion.
        if path_obj.is_file() and path_obj.suffix.lower() in SUPPORTED_EXTENSIONS:
            # This includes the file because it is directly ingestible.
            document_paths.append(path_obj)
            # This moves on because files do not need directory traversal.
            continue

        # This walks the directory tree so nested docs can be discovered automatically.
        if path_obj.is_dir():
            # This recursively scans the folder for supported files only.
            for nested_path in path_obj.rglob("*"):
                # This keeps only real files with supported extensions for parsing.
                if nested_path.is_file() and nested_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    # This stores the file so the ingest pipeline can process it later.
                    document_paths.append(nested_path.resolve())

    # This removes duplicates while preserving order so repeated inputs do not double-ingest files.
    unique_paths = list(dict.fromkeys(document_paths))

    # This returns the final ordered list of supported files to ingest.
    return unique_paths


def extract_text_from_file(file_path: str | Path) -> str:
    # This normalizes the incoming path so extension checks and metadata access are reliable.
    path_obj = Path(file_path).expanduser().resolve()
    # This reads the file extension once so branching stays clear below.
    suffix = path_obj.suffix.lower()

    # This parses PDFs page by page because they need a dedicated extraction library.
    if suffix == ".pdf":
        # This opens the PDF so each page's text can be extracted in order.
        pdf_document = fitz.open(path_obj)

        try:
            # This accumulates page text so the final string preserves document order.
            page_texts: list[str] = []

            # This loops through pages so every page contributes to the final document text.
            for page in pdf_document:
                # This extracts text from the current page so PDF content becomes searchable.
                page_texts.append(page.get_text())

            # This joins page text with spacing so chunking does not merge pages too aggressively.
            return "\n\n".join(page_texts).strip()
        finally:
            # This closes the PDF handle so file locks are released promptly.
            pdf_document.close()

    # This reads markdown and text files directly because their contents are already plain text.
    return path_obj.read_text(encoding="utf-8").strip()


def chunk_text(text: str, chunk_size: int = 1200, chunk_overlap: int = 200) -> list[str]:
    # This normalizes newlines so chunk boundaries stay predictable across operating systems.
    normalized_text = text.replace("\r\n", "\n").strip()

    # This returns early when a document contains no meaningful text to split.
    if not normalized_text:
        # This avoids creating empty chunks that would waste embeddings.
        return []

    # This stores the final chunk list that will be embedded and indexed.
    chunks: list[str] = []
    # This tracks the current window start as we slide through the document.
    start_index = 0
    # This stores the total text length so loop bounds stay cheap to evaluate.
    text_length = len(normalized_text)

    # This walks the text with overlap so retrieval can preserve context across chunk boundaries.
    while start_index < text_length:
        # This proposes a raw end position before we refine to a friendlier break point.
        end_index = min(start_index + chunk_size, text_length)

        # This prefers breaking on paragraph, newline, or sentence boundaries when possible.
        if end_index < text_length:
            # This inspects only the current window so we do not search the whole string repeatedly.
            window_text = normalized_text[start_index:end_index]

            # This finds the best natural split closest to the window end for better readability.
            split_offset = max(
                window_text.rfind("\n\n"),
                window_text.rfind("\n"),
                window_text.rfind(". "),
            )

            # This uses the natural boundary only when it is not too close to the window start.
            if split_offset > chunk_size // 2:
                # This moves the chunk end to the chosen boundary inside the current window.
                end_index = start_index + split_offset + 1

        # This extracts the current chunk candidate from the normalized text.
        chunk = normalized_text[start_index:end_index].strip()

        # This keeps only non-empty chunks so embeddings are always useful.
        if chunk:
            # This stores the chunk for later embedding and metadata assignment.
            chunks.append(chunk)

        # This stops when the end of the text is reached so the loop does not overrun.
        if end_index >= text_length:
            # This exits cleanly because there is no more text left to chunk.
            break

        # This advances with overlap so adjacent chunks share enough context for RAG quality.
        start_index = max(end_index - chunk_overlap, start_index + 1)

    # This returns chunked text ready for embedding and indexing.
    return chunks


def build_knowledge_base(
    paths: Sequence[str | Path],
    client: OpenAI,
    embedding_model: str = "text-embedding-3-small",
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
    embedding_batch_size: int = 64,
) -> IngestedKnowledgeBase:
    # This resolves all supported files first so downstream logic only handles real documents.
    document_paths = collect_document_paths(paths)

    # This fails loudly when there is nothing to ingest so setup problems surface immediately.
    if not document_paths:
        # This explains which file types are expected so the caller can fix their input quickly.
        raise ValueError("No supported documents found. Expected .pdf, .md, or .txt files.")

    # This will hold every chunk plus its metadata before vector indexing.
    chunks: list[SourceChunk] = []
    # This holds raw chunk text so embeddings can be requested in efficient batches.
    embedding_inputs: list[str] = []

    # This iterates each document so we can parse, chunk, and annotate it with source metadata.
    for path_obj in document_paths:
        # This extracts plain text from the current document for chunking.
        document_text = extract_text_from_file(path_obj)

        # This skips empty documents because they would not add any useful retrieval context.
        if not document_text:
            # This moves on so one blank file does not break the whole ingest run.
            continue

        # This splits the document into retrieval-sized windows with overlap for context carryover.
        document_chunks = chunk_text(
            text=document_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        # This skips documents that produced no usable chunks after parsing and cleanup.
        if not document_chunks:
            # This continues gracefully because there is still nothing meaningful to embed.
            continue

        # This reads file metadata once so every chunk can share consistent source details.
        modified_at = datetime.fromtimestamp(path_obj.stat().st_mtime, tz=timezone.utc)
        # This converts the timestamp into a stable string for UI display and API payloads.
        modified_at_iso = modified_at.isoformat()
        # This converts raw age into a simple label that is easier to surface in the product.
        freshness_tag = _build_freshness_tag(modified_at)

        # This walks each chunk so metadata can be attached before embedding.
        for chunk_index, chunk in enumerate(document_chunks):
            # This creates a stable identifier that combines the file stem with chunk order.
            chunk_id = f"{path_obj.stem}-{chunk_index}"

            # This stores chunk metadata so later retrieval can cite exact source details.
            chunks.append(
                SourceChunk(
                    source_path=str(path_obj),
                    source_name=path_obj.name,
                    chunk_id=chunk_id,
                    chunk_text=chunk,
                    chunk_index=chunk_index,
                    modified_at_iso=modified_at_iso,
                    freshness_tag=freshness_tag,
                )
            )

            # This stores raw chunk text in parallel so embedding requests stay batch-friendly.
            embedding_inputs.append(chunk)

    # This blocks setup when every document was empty because retrieval would be meaningless.
    if not chunks:
        # This explains the failure mode clearly so the caller can inspect their documents.
        raise ValueError("Documents were found, but none produced usable text chunks.")

    # This collects float vectors in ingestion order so chunk metadata and embeddings stay aligned.
    embedding_rows: list[list[float]] = []

    # This batches embedding requests so large doc sets stay within request size limits.
    for start_index in range(0, len(embedding_inputs), embedding_batch_size):
        # This slices the next batch of chunk text for a single embedding API request.
        batch_inputs = embedding_inputs[start_index : start_index + embedding_batch_size]

        # This builds embeddings for the batch so semantic search can compare chunk meaning.
        embedding_response = client.embeddings.create(
            model=embedding_model,
            input=batch_inputs,
        )

        # This appends each embedding row in API order so vectors still match their chunks.
        for item in embedding_response.data:
            # This stores the vector for later conversion into a FAISS matrix.
            embedding_rows.append(item.embedding)

    # This converts the embedding list into a contiguous float32 matrix for FAISS.
    embedding_matrix = np.asarray(embedding_rows, dtype="float32")

    # This normalizes every vector so inner product search behaves like cosine similarity.
    faiss.normalize_L2(embedding_matrix)

    # This creates an in-memory FAISS index sized to the embedding dimension.
    index = faiss.IndexFlatIP(embedding_matrix.shape[1])

    # This loads all embeddings into FAISS so search can run entirely in memory.
    index.add(embedding_matrix)

    # This returns the completed knowledge base ready for both onboarding agents.
    return IngestedKnowledgeBase(chunks=chunks, index=index)


def _build_freshness_tag(modified_at: datetime) -> str:
    # This measures age against the current UTC time so the label stays timezone-safe.
    age_in_days = (datetime.now(tz=timezone.utc) - modified_at).days

    # This treats recently updated docs as fresh for higher trust in surfaced guidance.
    if age_in_days <= 30:
        # This label is concise enough for a source badge in the UI.
        return "fresh"

    # This still marks moderately aged docs as recent rather than stale.
    if age_in_days <= 180:
        # This gives users a softer warning when docs are not brand new but still plausible.
        return "recent"

    # This flags older content so users know policy answers may need validation.
    return "stale"
