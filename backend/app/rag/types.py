from dataclasses import dataclass, field


@dataclass(slots=True)
class ChunkData:
    content: str
    chunk_index: int
    token_count: int
    metadata: dict


@dataclass(slots=True)
class RetrievedChunk:
    chunk_id: int
    document_id: int
    content: str
    filename: str
    chunk_index: int
    category: str
    score: float = 0.0
    rerank_score: float | None = None
    source_url: str | None = None


@dataclass(slots=True)
class RagAnswer:
    answer: str
    citations: list[dict] = field(default_factory=list)
    confidence_level: str = "中"
    insufficient_evidence: bool = False
    trace_id: str = ""
    fallback: bool = False
