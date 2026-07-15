from types import SimpleNamespace

from app.integrations import milvus as milvus_module


class FakeSchema:
    def __init__(self):
        self.fields = []

    def add_field(self, **kwargs):
        self.fields.append(kwargs)


class FakeIndexParams:
    def __init__(self):
        self.indexes = []

    def add_index(self, **kwargs):
        self.indexes.append(kwargs)


class FakeMilvusClient:
    instance = None

    def __init__(self, uri):
        self.uri = uri
        self.created = None
        self.upserted = []
        self.deleted = []
        FakeMilvusClient.instance = self

    @staticmethod
    def create_schema(**kwargs):
        return FakeSchema()

    def prepare_index_params(self):
        return FakeIndexParams()

    def has_collection(self, **kwargs):
        return self.created is not None

    def create_collection(self, **kwargs):
        self.created = kwargs

    def describe_collection(self, **kwargs):
        return {"fields": [{"name": "embedding", "params": {"dim": 3}}]}

    def load_collection(self, **kwargs):
        pass

    def upsert(self, **kwargs):
        self.upserted.extend(kwargs["data"])

    def flush(self, **kwargs):
        pass

    def search(self, **kwargs):
        return [[{"entity": {"chunk_id": 7}, "distance": 0.91}]]

    def delete(self, **kwargs):
        self.deleted.append(kwargs["filter"])

    def list_collections(self):
        return ["edu_chunks"] if self.created else []


def make_index(monkeypatch):
    monkeypatch.setattr(milvus_module, "MilvusClient", FakeMilvusClient)
    monkeypatch.setattr(milvus_module, "get_settings", lambda: SimpleNamespace(milvus_host="127.0.0.1", milvus_port=19530))
    monkeypatch.setattr(milvus_module, "get_model_runtime", lambda: SimpleNamespace(config=lambda: SimpleNamespace(
        vector_collection="edu_chunks", embedding_dimension=3,
    )))
    return milvus_module.MilvusIndex()


def test_milvus_client_creates_schema_and_uses_dict_upsert(monkeypatch):
    index = make_index(monkeypatch)
    index.upsert([{"chunk_id": 7, "course_id": 2, "document_id": 3, "category": "textbook",
                   "content_hash": "abc", "embedding": [0.1, 0.2, 0.3]}])
    client = FakeMilvusClient.instance
    assert client.uri == "http://127.0.0.1:19530"
    assert client.created["collection_name"] == "edu_chunks"
    assert client.upserted[0]["id"] == "7"
    assert index.search([0.1, 0.2, 0.3], 2, 5) == [(7, 0.91)]
    index.delete_document(3)
    assert client.deleted == ["document_id == 3"]
