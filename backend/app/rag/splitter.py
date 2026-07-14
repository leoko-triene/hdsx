import re

from app.rag.types import ChunkData


class RecursiveTextSplitter:
    """按字符近似 token 分割；中文约 1 字/token，英文约 4 字符/token。"""

    separators = ("\n\n", "\n", "。", "！", "？", ". ", " ")

    def __init__(self, chunk_size: int = 650, overlap: int = 100):
        if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
            raise ValueError("chunk_size 和 overlap 参数无效")
        self.chunk_size = chunk_size
        self.overlap = overlap

    @staticmethod
    def estimate_tokens(text: str) -> int:
        chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
        other = max(0, len(text) - chinese)
        return chinese + max(1, other // 4)

    def split(self, text: str, base_metadata: dict) -> list[ChunkData]:
        cleaned = re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n")).strip()
        if not cleaned:
            return []
        target_chars = self.chunk_size * 2
        overlap_chars = self.overlap * 2
        pieces = self._recursive_split(cleaned, target_chars, 0)
        chunks: list[str] = []
        current = ""
        for piece in pieces:
            if current and len(current) + len(piece) > target_chars:
                chunks.append(current.strip())
                current = current[-overlap_chars:] + piece
            else:
                current += piece
        if current.strip():
            chunks.append(current.strip())
        return [
            ChunkData(
                content=value,
                chunk_index=index,
                token_count=self.estimate_tokens(value),
                metadata={**base_metadata, "chunk_index": index},
            )
            for index, value in enumerate(chunks)
        ]

    def _recursive_split(self, text: str, limit: int, level: int) -> list[str]:
        if len(text) <= limit:
            return [text]
        if level >= len(self.separators):
            return [text[i : i + limit] for i in range(0, len(text), limit)]
        separator = self.separators[level]
        parts = text.split(separator)
        if len(parts) == 1:
            return self._recursive_split(text, limit, level + 1)
        result: list[str] = []
        for i, part in enumerate(parts):
            suffix = separator if i < len(parts) - 1 else ""
            result.extend(self._recursive_split(part + suffix, limit, level + 1))
        return result

