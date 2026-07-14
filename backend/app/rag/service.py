import hashlib
import json
import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.milvus import MilvusIndex
from app.integrations.llm import get_embedding_provider, get_llm_provider
from app.integrations.reranker import BGEReranker
from app.modules.models import Document, DocumentChunk
from app.rag.splitter import RecursiveTextSplitter
from app.rag.types import RagAnswer, RetrievedChunk


class KnowledgeService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def ingest_text(self, document: Document, content: str) -> int:
        splitter = RecursiveTextSplitter(
            self.settings.rag_chunk_size, self.settings.rag_chunk_overlap
        )
        chunks = splitter.split(
            content,
            {
                "source": document.source_path,
                "filename": document.filename,
                "category": document.category,
                "course_id": document.course_id,
            },
        )
        for chunk in chunks:
            self.db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    content_hash=hashlib.sha256(chunk.content.encode()).hexdigest(),
                    metadata_json=chunk.metadata,
                )
            )
        return len(chunks)

    async def index_document_vectors(self, document: Document) -> int:
        chunks = list(self.db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document.id)))
        if not chunks:
            return 0
        embeddings = await get_embedding_provider().embed([chunk.content for chunk in chunks])
        expected_dim = self.settings.embedding_dimension
        if any(len(vector) != expected_dim for vector in embeddings):
            raise ValueError(f"Embedding 向量维度不是预期的 {expected_dim}")
        MilvusIndex().upsert([
            {
                "chunk_id": chunk.id, "course_id": document.course_id,
                "document_id": document.id, "category": document.category,
                "content_hash": chunk.content_hash, "embedding": vector,
            }
            for chunk, vector in zip(chunks, embeddings, strict=True)
        ])
        for chunk in chunks:
            chunk.milvus_id = str(chunk.id)
        return len(chunks)

    def keyword_search(self, course_id: int, query: str, top_k: int = 20) -> list[RetrievedChunk]:
        # BOOLEAN MODE 对中文分词能力有限，首版同时提供 LIKE 兜底；检索适配层可替换为 ES。
        stmt = (
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.course_id == course_id, DocumentChunk.content.contains(query))
            .limit(top_k)
        )
        rows = self.db.execute(stmt).all()
        return [
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=doc.id,
                content=chunk.content,
                filename=doc.filename,
                chunk_index=chunk.chunk_index,
                category=doc.category,
                score=1.0 / (index + 1),
            )
            for index, (chunk, doc) in enumerate(rows)
        ]

    def course_context(self, course_id: int, top_k: int = 20) -> list[RetrievedChunk]:
        """Return representative ready chunks when a lesson topic is not a literal text match."""
        rows = self.db.execute(
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.course_id == course_id, Document.status == "ready")
            .order_by(Document.id.desc(), DocumentChunk.chunk_index)
            .limit(top_k)
        ).all()
        return [
            RetrievedChunk(
                chunk_id=chunk.id, document_id=doc.id, content=chunk.content,
                filename=doc.filename, chunk_index=chunk.chunk_index,
                category=doc.category, score=1.0 / (index + 1),
            )
            for index, (chunk, doc) in enumerate(rows)
        ]

    async def vector_search(self, course_id: int, query: str, top_k: int = 20) -> list[RetrievedChunk]:
        embedding = (await get_embedding_provider().embed([query]))[0]
        hits = MilvusIndex().search(embedding, course_id, top_k)
        if not hits:
            return []
        score_map = dict(hits)
        rows = self.db.execute(
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.id.in_(score_map))
        ).all()
        values = [
            RetrievedChunk(
                chunk_id=chunk.id, document_id=doc.id, content=chunk.content,
                filename=doc.filename, chunk_index=chunk.chunk_index, category=doc.category,
                score=score_map[chunk.id],
            ) for chunk, doc in rows
        ]
        return sorted(values, key=lambda item: item.score, reverse=True)

    @staticmethod
    def rrf_fusion(result_lists: list[list[RetrievedChunk]], k: int = 60) -> list[RetrievedChunk]:
        merged: dict[int, RetrievedChunk] = {}
        scores: dict[int, float] = {}
        for results in result_lists:
            for rank, item in enumerate(results, start=1):
                merged[item.chunk_id] = item
                scores[item.chunk_id] = scores.get(item.chunk_id, 0.0) + 1.0 / (k + rank)
        for chunk_id, item in merged.items():
            item.score = scores[chunk_id]
        return sorted(merged.values(), key=lambda item: item.score, reverse=True)

    async def hybrid_search(self, course_id: int, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        top_k = top_k or self.settings.rag_rerank_top_k
        keyword = self.keyword_search(course_id, query, self.settings.rag_keyword_top_k)
        try:
            vector = await self.vector_search(course_id, query, self.settings.rag_vector_top_k)
        except Exception:
            # 关键词检索仍可提供有依据结果；向量故障由健康检查暴露。
            vector = []
        candidates = self.rrf_fusion([vector, keyword])
        if not candidates:
            return []
        rerank_candidates = candidates[:30]
        scores = BGEReranker().score(query, [item.content for item in rerank_candidates])
        for item, score in zip(rerank_candidates, scores, strict=True):
            item.rerank_score = score
        candidates.sort(key=lambda item: item.rerank_score or item.score, reverse=True)
        return candidates[:top_k]

    async def answer(self, course_id: int, query: str) -> RagAnswer:
        trace_id = uuid.uuid4().hex
        chunks = await self.hybrid_search(course_id, query, self.settings.rag_rerank_top_k)
        if not chunks:
            return RagAnswer(
                answer="当前课程知识库中没有找到足够依据，请补充资料或转交教师。",
                insufficient_evidence=True,
                trace_id=trace_id,
            )
        context = "\n\n".join(
            f"[资料{i + 1}|chunk_id={c.chunk_id}|{c.filename}]\n{c.content}" for i, c in enumerate(chunks)
        )
        prompt = f"问题：{query}\n\n可用资料：\n{context}\n\n请只依据资料回答，并使用[资料N]标注引用。"
        answer = await get_llm_provider().chat(
            "你是严谨的课程答疑助手。证据不足时必须说明，不得编造。", prompt
        )
        citations = [
            {"chunk_id": c.chunk_id, "filename": c.filename, "chunk_index": c.chunk_index}
            for c in chunks
        ]
        return RagAnswer(answer=answer, citations=citations, confidence=0.75, trace_id=trace_id)
