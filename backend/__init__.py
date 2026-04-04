# This re-exports the main backend entry points so consumers can import from `backend` directly.
from .agents import KnowledgeAgents, QuestionAnswer, RoleBrief
# This re-exports the ingestion primitives so advanced callers can customize indexing if needed.
from .ingest import IngestedKnowledgeBase, SearchResult, SourceChunk, build_knowledge_base

__all__ = [
    "IngestedKnowledgeBase",
    "KnowledgeAgents",
    "QuestionAnswer",
    "RoleBrief",
    "SearchResult",
    "SourceChunk",
    "build_knowledge_base",
]
