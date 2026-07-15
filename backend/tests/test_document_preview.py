from types import SimpleNamespace
from pathlib import Path

from app.api import router as router_module


class FakeDB:
    def __init__(self, document, chunks):
        self.document = document
        self.chunks = chunks

    def get(self, model, document_id):
        return self.document if self.document.id == document_id else None

    def scalars(self, statement):
        return self.chunks


def test_document_preview_reassembles_chunks_and_marks_markdown(monkeypatch):
    monkeypatch.setattr(router_module, "visible_course", lambda *args: None)
    document = SimpleNamespace(id=7, course_id=3, status="ready", filename="chapter.md", mime_type="text/markdown", category="textbook", source_url=None)
    chunks = [SimpleNamespace(content="# 标题"), SimpleNamespace(content="正文内容")]
    result = router_module.preview_document(3, 7, FakeDB(document, chunks), SimpleNamespace(id=1))
    assert result["format"] == "markdown"
    assert result["content"] == "# 标题\n\n正文内容"
    assert result["chunks"] == 2
    assert result["truncated"] is False


def test_document_preview_removes_splitter_overlap(monkeypatch):
    monkeypatch.setattr(router_module, "visible_course", lambda *args: None)
    document = SimpleNamespace(id=8, course_id=3, status="ready", filename="note.txt", mime_type="text/plain", category="textbook", source_url=None)
    repeated = "这是需要去重的重叠内容一共超过二十个字符。"
    chunks = [SimpleNamespace(content="第一段。" + repeated), SimpleNamespace(content=repeated + "第二段。")]
    result = router_module.preview_document(3, 8, FakeDB(document, chunks), SimpleNamespace(id=1))
    assert result["content"].count(repeated) == 1
    assert result["format"] == "text"


def test_document_preview_reads_original_text_with_gb18030(monkeypatch, tmp_path):
    monkeypatch.setattr(router_module, "visible_course", lambda *args: None)
    monkeypatch.setattr(router_module, "get_settings", lambda: SimpleNamespace(storage_root=tmp_path, api_prefix="/api/v1"))
    path = tmp_path / "中文.txt"
    path.write_bytes("中文编码预览正常".encode("gb18030"))
    document = SimpleNamespace(id=9, course_id=3, status="ready", filename="中文.txt", mime_type="text/plain",
                               category="textbook", source_url=None, source_path=str(path))
    result = router_module.preview_document(3, 9, FakeDB(document, []), SimpleNamespace(id=1))
    assert result["format"] == "text"
    assert result["content"] == "中文编码预览正常"


def test_document_preview_selects_pdf_and_word_modes(monkeypatch, tmp_path):
    monkeypatch.setattr(router_module, "visible_course", lambda *args: None)
    monkeypatch.setattr(router_module, "get_settings", lambda: SimpleNamespace(storage_root=tmp_path, api_prefix="/api/v1"))
    pdf_path = tmp_path / "讲义.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 test")
    pdf = SimpleNamespace(id=10, course_id=3, status="ready", filename="讲义.pdf", mime_type="application/pdf",
                          category="textbook", source_url=None, source_path=str(pdf_path))
    result = router_module.preview_document(3, 10, FakeDB(pdf, []), SimpleNamespace(id=1))
    assert result["format"] == "pdf"
    assert result["content_url"].endswith("/documents/10/content")

    docx = SimpleNamespace(id=11, course_id=3, status="ready", filename="讲义.docx",
                           mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                           category="textbook", source_url=None, source_path=str(tmp_path / "missing.docx"))
    result = router_module.preview_document(3, 11, FakeDB(docx, [SimpleNamespace(content="Word 正文")]), SimpleNamespace(id=1))
    assert result["format"] == "word"
    assert result["content"] == "Word 正文"
