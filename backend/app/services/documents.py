import hashlib
import io
from pathlib import Path

from fastapi import UploadFile

from app.core.exceptions import AppError


def extract_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md"}:
        for encoding in ("utf-8", "gb18030"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
    elif suffix == ".pdf":
        try:
            from pypdf import PdfReader
            return "\n\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
        except Exception as exc:
            raise AppError("DOCUMENT_PARSE_FAILED", f"PDF 解析失败：{exc}", 422) from exc
    elif suffix == ".docx":
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as exc:
            raise AppError("DOCUMENT_PARSE_FAILED", f"DOCX 解析失败：{exc}", 422) from exc
    raise AppError("UNSUPPORTED_FILE", "仅支持 TXT、Markdown、PDF 和 DOCX", 415)


async def read_upload(upload: UploadFile, max_mb: int) -> tuple[bytes, str]:
    data = await upload.read()
    if len(data) > max_mb * 1024 * 1024:
        raise AppError("FILE_TOO_LARGE", f"文件不能超过 {max_mb}MB", 413)
    if not data:
        raise AppError("EMPTY_FILE", "上传文件为空", 422)
    return data, hashlib.sha256(data).hexdigest()

