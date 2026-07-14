from app.rag.service import KnowledgeService
from app.rag.types import RetrievedChunk


def chunk(chunk_id: int, score: float = 0.0):
    return RetrievedChunk(chunk_id, 1, f"content-{chunk_id}", "demo.txt", chunk_id, "textbook", score)


def test_rrf_merges_and_deduplicates():
    result = KnowledgeService.rrf_fusion([[chunk(1), chunk(2)], [chunk(2), chunk(3)]])
    assert [item.chunk_id for item in result][0] == 2
    assert {item.chunk_id for item in result} == {1, 2, 3}

