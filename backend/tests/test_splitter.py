from app.rag.splitter import RecursiveTextSplitter


def test_recursive_splitter_metadata_and_overlap():
    splitter = RecursiveTextSplitter(chunk_size=20, overlap=5)
    chunks = splitter.split("第一段内容。" * 30, {"source": "demo", "filename": "a.txt", "category": "textbook"})
    assert len(chunks) > 1
    assert [x.chunk_index for x in chunks] == list(range(len(chunks)))
    assert all(x.metadata["filename"] == "a.txt" for x in chunks)
    assert all(x.token_count > 0 for x in chunks)


def test_recursive_splitter_rejects_invalid_parameters():
    import pytest
    with pytest.raises(ValueError): RecursiveTextSplitter(100, 100)

