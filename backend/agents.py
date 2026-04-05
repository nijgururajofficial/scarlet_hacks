from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

try:
    from .ingest import IngestedKnowledgeBase, SearchResult, SourceChunk, build_knowledge_base
    from .prompts import (
        build_answer_user_prompt,
        build_brief_system_prompt,
        build_brief_user_prompt,
        build_search_system_prompt,
        normalize_role,
    )
except ImportError:
    from ingest import IngestedKnowledgeBase, SearchResult, SourceChunk, build_knowledge_base
    from prompts import (
        build_answer_user_prompt,
        build_brief_system_prompt,
        build_brief_user_prompt,
        build_search_system_prompt,
        normalize_role,
    )

DEFAULT_RESPONSE_MODEL = "gpt-4.1-mini"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


@dataclass(slots=True)
class RoleBrief:
    role: str
    must_knows: list[str]
    tools_checklist: list[str]
    key_contacts: list[dict[str, str]]
    roadmap: dict[str, list[str]]
    source_docs: list[str]


@dataclass(slots=True)
class QuestionAnswer:
    answer: str
    action: str | None
    who_to_contact: str | None
    risk_level: str | None
    next_steps: list[str]
    source_docs: list[str]
    freshness: list[dict[str, str]]
    retrieved_chunks: list[SearchResult]


class KnowledgeAgents:
    def __init__(
        self,
        client: OpenAI,
        knowledge_base: IngestedKnowledgeBase,
        response_model: str = DEFAULT_RESPONSE_MODEL,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        self.client = client
        self.knowledge_base = knowledge_base
        self.response_model = response_model
        self.embedding_model = embedding_model

    @classmethod
    def from_document_paths(
        cls,
        document_paths: list[str],
        response_model: str = DEFAULT_RESPONSE_MODEL,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> "KnowledgeAgents":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("Set OPENAI_API_KEY before building the backend knowledge base.")

        client = OpenAI(api_key=api_key)
        knowledge_base = build_knowledge_base(
            paths=document_paths,
            client=client,
            embedding_model=embedding_model,
        )

        return cls(
            client=client,
            knowledge_base=knowledge_base,
            response_model=response_model,
            embedding_model=embedding_model,
        )

    def generate_role_brief(self, role: str) -> RoleBrief:
        normalized_role = normalize_role(role)
        selected_chunks = self.knowledge_base.select_brief_chunks()
        context_block = _format_chunk_context(selected_chunks)
        system_prompt = build_brief_system_prompt(normalized_role)
        user_prompt = build_brief_user_prompt(context_block)

        response = self.client.responses.create(
            model=self.response_model,
            instructions=system_prompt,
            input=user_prompt,
        )

        response_text = _extract_response_text(response)
        source_docs = _dedupe_in_order([chunk.source_name for chunk in selected_chunks])

        return _parse_brief_payload(
            response_text=response_text,
            normalized_role=normalized_role,
            fallback_source_docs=source_docs,
        )

    def answer_question(self, role: str, question: str, top_k: int = 5) -> QuestionAnswer:
        normalized_role = normalize_role(role)
        retrieved_chunks = self.knowledge_base.retrieve(
            query=question,
            client=self.client,
            top_k=top_k,
            embedding_model=self.embedding_model,
        )

        if not retrieved_chunks:
            return QuestionAnswer(
                answer="I could not find a grounded answer in the uploaded company documents.",
                action=None,
                who_to_contact=None,
                risk_level=None,
                next_steps=[],
                source_docs=[],
                freshness=[],
                retrieved_chunks=[],
            )

        context_block = _format_search_context(retrieved_chunks)
        system_prompt = build_search_system_prompt(normalized_role)
        user_prompt = build_answer_user_prompt(
            question=question,
            context_block=context_block,
            role=normalized_role,
        )

        response = self.client.responses.create(
            model=self.response_model,
            instructions=system_prompt,
            input=user_prompt,
        )

        fallback_source_docs = _dedupe_in_order(
            [search_result.chunk.source_name for search_result in retrieved_chunks]
        )
        freshness = _build_freshness_payload(retrieved_chunks)
        response_text = _extract_response_text(response)
        parsed_answer = _parse_answer_payload(
            response_text=response_text,
            fallback_source_docs=fallback_source_docs,
        )

        return QuestionAnswer(
            answer=parsed_answer["answer"],
            action=parsed_answer["action"],
            who_to_contact=parsed_answer["who_to_contact"],
            risk_level=parsed_answer["risk_level"],
            next_steps=parsed_answer["next_steps"],
            source_docs=parsed_answer["sources"],
            freshness=freshness,
            retrieved_chunks=retrieved_chunks,
        )


def _format_chunk_context(chunks: list[SourceChunk]) -> str:
    context_sections: list[str] = []

    for chunk in chunks:
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

    return "\n\n---\n\n".join(context_sections)


def _format_search_context(retrieved_chunks: list[SearchResult]) -> str:
    context_sections: list[str] = []

    for search_result in retrieved_chunks:
        chunk = search_result.chunk
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

    return "\n\n---\n\n".join(context_sections)


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", "")
    if output_text:
        return output_text.strip()

    output_items = getattr(response, "output", [])
    text_parts: list[str] = []

    for output_item in output_items:
        content_items = getattr(output_item, "content", [])
        for content_item in content_items:
            text_value = getattr(content_item, "text", "")
            if text_value:
                text_parts.append(str(text_value).strip())

    return "\n".join(part for part in text_parts if part).strip()


def _parse_brief_payload(
    response_text: str,
    normalized_role: str,
    fallback_source_docs: list[str],
) -> RoleBrief:
    cleaned_text = response_text.strip()

    if cleaned_text.startswith("```"):
        cleaned_text = cleaned_text.strip("`")
        cleaned_text = cleaned_text.removeprefix("json").strip()

    try:
        payload = json.loads(cleaned_text)
    except json.JSONDecodeError:
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

    must_knows = [str(item) for item in payload.get("must_knows", [])]
    tools_checklist = [str(item) for item in payload.get("tools_checklist", [])]
    key_contacts = [
        {
            "name": str(item.get("name", "")),
            "reason": str(item.get("reason", "")),
            "source": str(item.get("source", "")),
        }
        for item in payload.get("key_contacts", [])
        if isinstance(item, dict)
    ]

    roadmap_payload = payload.get("roadmap", {})
    roadmap = {
        "week_1": [str(item) for item in roadmap_payload.get("week_1", [])],
        "week_2": [str(item) for item in roadmap_payload.get("week_2", [])],
        "week_3_4": [str(item) for item in roadmap_payload.get("week_3_4", [])],
    }

    source_docs = payload.get("source_docs") or fallback_source_docs

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
    cleaned_text = response_text.strip()

    if cleaned_text.startswith("```"):
        cleaned_text = cleaned_text.strip("`")
        cleaned_text = cleaned_text.removeprefix("json").strip()

    try:
        payload = json.loads(cleaned_text)
    except json.JSONDecodeError:
        return {
            "answer": response_text,
            "action": None,
            "who_to_contact": None,
            "risk_level": None,
            "next_steps": [],
            "sources": fallback_source_docs,
        }

    answer = str(payload.get("answer", "")).strip()
    action = _coerce_optional_string(payload.get("action"))
    who_to_contact = _coerce_optional_string(payload.get("who_to_contact"))
    risk_level = _coerce_optional_string(payload.get("risk_level"))
    next_steps = [str(item) for item in payload.get("next_steps", [])]
    source_docs = payload.get("sources") or fallback_source_docs

    return {
        "answer": answer or "I could not produce a grounded answer from the retrieved context.",
        "action": action,
        "who_to_contact": who_to_contact,
        "risk_level": risk_level if risk_level in {"low", "medium", "high"} else None,
        "next_steps": next_steps,
        "sources": [str(item) for item in source_docs],
    }


def _coerce_optional_string(value: Any) -> str | None:
    if value is None:
        return None

    normalized_value = str(value).strip()
    if normalized_value.lower() in {"", "null", "none"}:
        return None

    return normalized_value


def _build_freshness_payload(retrieved_chunks: list[SearchResult]) -> list[dict[str, str]]:
    freshness_by_source: dict[str, dict[str, str]] = {}

    for search_result in retrieved_chunks:
        chunk = search_result.chunk
        freshness_by_source.setdefault(
            chunk.source_name,
            {
                "source": chunk.source_name,
                "freshness": chunk.freshness_tag,
                "modified_at": chunk.modified_at_iso,
            },
        )

    return list(freshness_by_source.values())


def _dedupe_in_order(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))
