from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

# This prefers package-relative imports when the backend is imported as a Python package.
try:
    # This imports sibling modules through the package so `import backend` works cleanly.
    from .ingest import IngestedKnowledgeBase, SearchResult, SourceChunk, build_knowledge_base
    # This imports prompt helpers through the package so the module stays package-friendly.
    from .prompts import (
        build_answer_user_prompt,
        build_brief_system_prompt,
        build_brief_user_prompt,
        build_search_system_prompt,
        normalize_role,
    )
except ImportError:
    # This falls back to local imports so running files directly from the backend folder still works.
    from ingest import IngestedKnowledgeBase, SearchResult, SourceChunk, build_knowledge_base
    # This falls back to local prompt imports for the same standalone execution path.
    from prompts import (
        build_answer_user_prompt,
        build_brief_system_prompt,
        build_brief_user_prompt,
        build_search_system_prompt,
        normalize_role,
    )

# This default keeps the backend runnable without forcing the UI to pass a model every time.
DEFAULT_RESPONSE_MODEL = "gpt-4.1-mini"
# This default keeps retrieval affordable while still supporting decent semantic search quality.
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


@dataclass(slots=True)
class RoleBrief:
    # This repeats the role so the UI can render the brief without extra state lookups.
    role: str
    # This stores the top onboarding points the new hire should understand immediately.
    must_knows: list[str]
    # This stores tools or systems the role should set up early.
    tools_checklist: list[str]
    # This stores key people plus why they matter so the UI can render simple contact cards.
    key_contacts: list[dict[str, str]]
    # This stores a week-based onboarding roadmap for quick card rendering.
    roadmap: dict[str, list[str]]
    # This stores source document names so the brief can show provenance.
    source_docs: list[str]


@dataclass(slots=True)
class QuestionAnswer:
    # This stores the grounded answer text returned by Agent 2.
    answer: str
    # This stores the clearest next action so the UI can surface a concise recommendation.
    action: str
    # This stores the best contact or owning team when the user needs a handoff.
    who_to_contact: str
    # This stores the answer risk level so the UI can highlight sensitive guidance.
    risk_level: str
    # This stores a simple confidence score so missing or conflicting info can be surfaced.
    confidence: float
    # This stores suggested follow-up steps so the UI can feel more actionable.
    next_steps: list[str]
    # This stores source names so the UI can surface document provenance on every answer.
    source_docs: list[str]
    # This stores freshness summaries so the UI can show how recent the cited docs are.
    freshness: list[dict[str, str]]
    # This stores the retrieved chunks for optional expandable citations in the UI.
    retrieved_chunks: list[SearchResult]


class KnowledgeAgents:
    # This object bundles the shared client and knowledge base so both agents use the same backend state.
    def __init__(
        self,
        client: OpenAI,
        knowledge_base: IngestedKnowledgeBase,
        response_model: str = DEFAULT_RESPONSE_MODEL,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        # This stores the OpenAI client so both agents can create responses and embeddings.
        self.client = client
        # This stores the shared FAISS-backed knowledge base for both proactive and search flows.
        self.knowledge_base = knowledge_base
        # This stores the generation model so callers can override it per environment if needed.
        self.response_model = response_model
        # This stores the embedding model so query retrieval matches ingestion settings.
        self.embedding_model = embedding_model

    @classmethod
    def from_document_paths(
        cls,
        document_paths: list[str],
        response_model: str = DEFAULT_RESPONSE_MODEL,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> "KnowledgeAgents":
        # This reads the API key once so setup fails fast before any expensive work starts.
        api_key = os.getenv("OPENAI_API_KEY")

        # This enforces a clear setup requirement because the backend cannot run without credentials.
        if not api_key:
            # This explains the missing environment variable directly so local setup is easy to fix.
            raise EnvironmentError("Set OPENAI_API_KEY before building the backend knowledge base.")

        # This initializes the OpenAI client so embeddings and responses share the same credentials.
        client = OpenAI(api_key=api_key)

        # This builds the in-memory FAISS knowledge base from the provided document paths.
        knowledge_base = build_knowledge_base(
            paths=document_paths,
            client=client,
            embedding_model=embedding_model,
        )

        # This returns a fully wired agent bundle ready for both backend flows.
        return cls(
            client=client,
            knowledge_base=knowledge_base,
            response_model=response_model,
            embedding_model=embedding_model,
        )

    def generate_role_brief(self, role: str) -> RoleBrief:
        # This normalizes the role once so prompt builders and response payloads stay aligned.
        normalized_role = normalize_role(role)

        # This pulls a balanced slice of chunks so the brief sees broad document coverage.
        selected_chunks = self.knowledge_base.select_brief_chunks()

        # This formats the retrieved chunks into a readable context block for the model.
        context_block = _format_chunk_context(selected_chunks)

        # This builds the role-specific brief system prompt so the model knows the exact task.
        system_prompt = build_brief_system_prompt(normalized_role)
        # This builds the user prompt carrying the knowledge context the model should synthesize.
        user_prompt = build_brief_user_prompt(context_block)

        # This asks the model to synthesize a structured onboarding brief from the selected docs.
        response = self.client.responses.create(
            model=self.response_model,
            instructions=system_prompt,
            input=user_prompt,
        )

        # This extracts plain text from the response object so we can parse the JSON payload.
        response_text = _extract_response_text(response)

        # This collects source names in display order so the final brief can cite its inputs.
        source_docs = _dedupe_in_order([chunk.source_name for chunk in selected_chunks])

        # This parses the model output into a predictable brief shape for the UI.
        return _parse_brief_payload(
            response_text=response_text,
            normalized_role=normalized_role,
            fallback_source_docs=source_docs,
        )

    def answer_question(self, role: str, question: str, top_k: int = 5) -> QuestionAnswer:
        # This normalizes the role once so prompt wording and role checks stay consistent.
        normalized_role = normalize_role(role)

        # This retrieves the most relevant chunks for the current question using semantic search.
        retrieved_chunks = self.knowledge_base.retrieve(
            query=question,
            client=self.client,
            top_k=top_k,
            embedding_model=self.embedding_model,
        )

        # This handles empty retrieval cleanly so the UI still gets a structured response object.
        if not retrieved_chunks:
            # This returns a graceful fallback because there was no useful evidence to ground an answer.
            return QuestionAnswer(
                answer="I could not find a grounded answer in the uploaded company documents.",
                action="Ask the document owner to add or clarify the missing information.",
                who_to_contact="The document owner or onboarding lead",
                risk_level="medium",
                confidence=0.0,
                next_steps=[
                    "Check whether the relevant policy or process document has been uploaded.",
                    "Ask the onboarding lead for the missing source of truth.",
                ],
                source_docs=[],
                freshness=[],
                retrieved_chunks=[],
            )

        # This formats the retrieved evidence into a compact context block for grounded answering.
        context_block = _format_search_context(retrieved_chunks)

        # This builds the role-specific system prompt so the answer respects role boundaries.
        system_prompt = build_search_system_prompt(normalized_role)
        # This builds the user prompt combining the question and retrieved context.
        user_prompt = build_answer_user_prompt(question=question, context_block=context_block)

        # This asks the model to answer from retrieved evidence instead of relying on prior knowledge.
        response = self.client.responses.create(
            model=self.response_model,
            instructions=system_prompt,
            input=user_prompt,
        )

        # This deduplicates cited source names so the UI can show clean source tags.
        fallback_source_docs = _dedupe_in_order(
            [search_result.chunk.source_name for search_result in retrieved_chunks]
        )

        # This builds simple freshness metadata so the UI can badge each cited document.
        freshness = _build_freshness_payload(retrieved_chunks)

        # This extracts plain text from the model response so the structured payload can be parsed.
        response_text = _extract_response_text(response)

        # This parses the model output into the richer answer contract used by the API and UI.
        parsed_answer = _parse_answer_payload(
            response_text=response_text,
            fallback_source_docs=fallback_source_docs,
        )

        # This returns the full grounded answer bundle for the frontend or API layer.
        return QuestionAnswer(
            answer=parsed_answer["answer"],
            action=parsed_answer["action"],
            who_to_contact=parsed_answer["who_to_contact"],
            risk_level=parsed_answer["risk_level"],
            confidence=parsed_answer["confidence"],
            next_steps=parsed_answer["next_steps"],
            source_docs=parsed_answer["sources"],
            freshness=freshness,
            retrieved_chunks=retrieved_chunks,
        )


def _format_chunk_context(chunks: list[SourceChunk]) -> str:
    # This stores formatted context sections so they can be joined into one prompt block.
    context_sections: list[str] = []

    # This walks each chunk so the model sees source metadata alongside the actual text.
    for chunk in chunks:
        # This formats metadata and content together so synthesis stays grounded to source docs.
        context_sections.append(
            "\n".join(
                [
                    f"Source: {chunk.source_name}",
                    f"Freshness: {chunk.freshness_tag}",
                    f"Modified At: {chunk.modified_at_iso}",
                    f"Chunk ID: {chunk.chunk_id}",
                    "Content:",
                    chunk.chunk_text,
                ]
            )
        )

    # This joins sections with visible spacing so prompt boundaries stay readable to the model.
    return "\n\n---\n\n".join(context_sections)


def _format_search_context(retrieved_chunks: list[SearchResult]) -> str:
    # This stores formatted retrieval sections so the answering prompt stays easy to inspect.
    context_sections: list[str] = []

    # This walks ranked search results so the model sees evidence in retrieval order.
    for search_result in retrieved_chunks:
        # This pulls the underlying chunk once so repeated attribute access stays shorter.
        chunk = search_result.chunk

        # This formats metadata, score, and content together so the answer can cite the right evidence.
        context_sections.append(
            "\n".join(
                [
                    f"Source: {chunk.source_name}",
                    f"Freshness: {chunk.freshness_tag}",
                    f"Modified At: {chunk.modified_at_iso}",
                    f"Similarity Score: {search_result.score:.4f}",
                    "Content:",
                    chunk.chunk_text,
                ]
            )
        )

    # This joins sections with separators so the model can distinguish different retrieved chunks.
    return "\n\n---\n\n".join(context_sections)


def _extract_response_text(response: Any) -> str:
    # This prefers the SDK convenience property because it is the most stable plain-text accessor.
    output_text = getattr(response, "output_text", "")

    # This returns immediately when the convenience property already contains the model output.
    if output_text:
        # This strips trailing whitespace so UI rendering stays tidy.
        return output_text.strip()

    # This falls back to walking response output items because some SDK versions expose text there.
    output_items = getattr(response, "output", [])

    # This accumulates text fragments so alternate response shapes still collapse into one string.
    text_parts: list[str] = []

    # This inspects each output item because the SDK may nest text segments by content block.
    for output_item in output_items:
        # This reads the content array defensively so missing fields do not crash extraction.
        content_items = getattr(output_item, "content", [])

        # This inspects each content item so text fragments can be collected in order.
        for content_item in content_items:
            # This reads the segment text if present in the current SDK object shape.
            text_value = getattr(content_item, "text", "")

            # This keeps non-empty text fragments only so the final string stays clean.
            if text_value:
                # This stores the fragment in order so the reconstructed answer remains coherent.
                text_parts.append(str(text_value).strip())

    # This joins the collected fragments into the final response string.
    return "\n".join(part for part in text_parts if part).strip()


def _parse_brief_payload(
    response_text: str,
    normalized_role: str,
    fallback_source_docs: list[str],
) -> RoleBrief:
    # This starts with the raw model output so we can repair simple fenced JSON cases.
    cleaned_text = response_text.strip()

    # This removes markdown fences because the UI expects parsed JSON rather than code formatting.
    if cleaned_text.startswith("```"):
        # This strips common fence characters so json.loads gets a cleaner payload.
        cleaned_text = cleaned_text.strip("`")
        # This removes a leading json label when the model includes one inside the fence.
        cleaned_text = cleaned_text.removeprefix("json").strip()

    try:
        # This parses the model output into Python data for validation and fallback handling.
        payload = json.loads(cleaned_text)
    except json.JSONDecodeError:
        # This returns a safe fallback brief so the UI still receives a usable object shape.
        return RoleBrief(
            role=normalized_role,
            must_knows=[response_text],
            tools_checklist=[],
            key_contacts=[],
            roadmap={
                "week_1": [],
                "week_2": [],
                "week_3_4": [],
            },
            source_docs=fallback_source_docs,
        )

    # This reads must-knows defensively so malformed payloads do not break the response shape.
    must_knows = [str(item) for item in payload.get("must_knows", [])]
    # This reads the tool checklist defensively so missing keys do not crash the backend.
    tools_checklist = [str(item) for item in payload.get("tools_checklist", [])]

    # This rebuilds contacts as string dictionaries so the UI can trust the field types.
    key_contacts = [
        {
            "name": str(item.get("name", "")),
            "reason": str(item.get("reason", "")),
            "source": str(item.get("source", "")),
        }
        for item in payload.get("key_contacts", [])
        if isinstance(item, dict)
    ]

    # This reads the roadmap payload once so each week field can be normalized safely.
    roadmap_payload = payload.get("roadmap", {})

    # This normalizes roadmap fields so the frontend always receives the same keys.
    roadmap = {
        "week_1": [str(item) for item in roadmap_payload.get("week_1", [])],
        "week_2": [str(item) for item in roadmap_payload.get("week_2", [])],
        "week_3_4": [str(item) for item in roadmap_payload.get("week_3_4", [])],
    }

    # This prefers model-provided source docs but falls back to retrieval-derived sources if absent.
    source_docs = payload.get("source_docs") or fallback_source_docs

    # This returns a validated brief object that matches the backend contract.
    return RoleBrief(
        role=str(payload.get("role", normalized_role)),
        must_knows=must_knows,
        tools_checklist=tools_checklist,
        key_contacts=key_contacts,
        roadmap=roadmap,
        source_docs=[str(item) for item in source_docs],
    )


def _parse_answer_payload(
    response_text: str,
    fallback_source_docs: list[str],
) -> dict[str, Any]:
    # This starts with the raw model output so simple fenced JSON can be repaired before parsing.
    cleaned_text = response_text.strip()

    # This removes markdown fences because the frontend expects structured fields rather than code blocks.
    if cleaned_text.startswith("```"):
        # This strips common fence characters so json.loads gets a cleaner payload.
        cleaned_text = cleaned_text.strip("`")
        # This removes a leading json label when the model includes one inside the fence.
        cleaned_text = cleaned_text.removeprefix("json").strip()

    try:
        # This parses the model output into a dictionary so structured decision fields can be extracted.
        payload = json.loads(cleaned_text)
    except json.JSONDecodeError:
        # This falls back to a predictable structure so the UI still receives a usable response.
        return {
            "answer": response_text,
            "action": "Verify the answer with the relevant team before taking action.",
            "who_to_contact": "The team or document owner responsible for this process",
            "risk_level": "medium",
            "confidence": 0.3,
            "next_steps": [
                "Review the cited documents manually.",
                "Ask the relevant owner to confirm the process.",
            ],
            "sources": fallback_source_docs,
        }

    # This extracts the model-provided answer text while defaulting safely if the field is missing.
    answer = str(payload.get("answer", "")).strip()
    # This extracts the recommended action so the UI can surface it prominently.
    action = str(payload.get("action", "")).strip()
    # This extracts the contact recommendation so handoffs are explicit.
    who_to_contact = str(payload.get("who_to_contact", "")).strip()
    # This normalizes the risk level so the UI receives a predictable lowercase badge value.
    risk_level = str(payload.get("risk_level", "medium")).strip().lower() or "medium"

    # This reads the raw confidence value so it can be coerced into a safe float range.
    raw_confidence = payload.get("confidence", 0.5)

    try:
        # This converts confidence into a float so the frontend can render it consistently.
        confidence = float(raw_confidence)
    except (TypeError, ValueError):
        # This falls back to a neutral confidence when the model returns an invalid value.
        confidence = 0.5

    # This clamps confidence into the expected range so the contract stays stable.
    confidence = max(0.0, min(1.0, confidence))

    # This normalizes next steps into strings so the UI can render them as bullet points.
    next_steps = [str(item) for item in payload.get("next_steps", [])]
    # This prefers model-cited sources but falls back to retrieval-derived sources when needed.
    source_docs = payload.get("sources") or fallback_source_docs

    # This returns the normalized structured answer payload for the API response layer.
    return {
        "answer": answer or "I could not produce a grounded answer from the retrieved context.",
        "action": action or "Review the relevant documents and confirm the next action with the owner.",
        "who_to_contact": who_to_contact or "The relevant process owner",
        "risk_level": risk_level if risk_level in {"low", "medium", "high"} else "medium",
        "confidence": confidence,
        "next_steps": next_steps,
        "sources": [str(item) for item in source_docs],
    }


def _build_freshness_payload(retrieved_chunks: list[SearchResult]) -> list[dict[str, str]]:
    # This stores per-source freshness metadata so duplicate chunks do not create duplicate badges.
    freshness_by_source: dict[str, dict[str, str]] = {}

    # This walks retrieved chunks so we can collect freshness once per source document.
    for search_result in retrieved_chunks:
        # This pulls the chunk object once so field access stays compact below.
        chunk = search_result.chunk

        # This stores the first seen metadata for the source because retrieval is already rank ordered.
        freshness_by_source.setdefault(
            chunk.source_name,
            {
                "source": chunk.source_name,
                "freshness": chunk.freshness_tag,
                "modified_at": chunk.modified_at_iso,
            },
        )

    # This returns freshness entries in first-seen order for stable UI rendering.
    return list(freshness_by_source.values())


def _dedupe_in_order(items: list[str]) -> list[str]:
    # This keeps ordered unique values so repeated source names do not clutter the UI.
    return list(dict.fromkeys(items))
