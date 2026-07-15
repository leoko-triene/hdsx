from app.rag.types import RetrievedChunk


def positive_evidence(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """保留所有片段，仅按重排分数排序；BGE 对长中文问句可能返回低分但不代表不相关。"""
    return chunks


def diverse_evidence(chunks: list[RetrievedChunk], per_document: int = 3) -> list[RetrievedChunk]:
    """过滤过短片段，并限制单一文件占满结果列表。"""
    counts: dict[int, int] = {}
    selected: list[RetrievedChunk] = []
    for item in chunks:
        if len(item.content.strip()) < 20 or counts.get(item.document_id, 0) >= per_document:
            continue
        selected.append(item)
        counts[item.document_id] = counts.get(item.document_id, 0) + 1
    return selected
