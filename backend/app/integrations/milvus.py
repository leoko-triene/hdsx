from threading import Lock

from pymilvus import DataType, MilvusClient

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.integrations.model_runtime import get_model_runtime


class MilvusIndex:
    """基于 MilvusClient 的向量索引，避免已弃用的 ORM API。"""

    _lock = Lock()

    def __init__(self):
        self.settings = get_settings()
        self.model_config = get_model_runtime().config()
        self._client: MilvusClient | None = None

    def connect(self) -> MilvusClient:
        if self._client is None:
            self._client = MilvusClient(
                uri=f"http://{self.settings.milvus_host}:{self.settings.milvus_port}"
            )
        return self._client

    @staticmethod
    def _embedding_dimension(description: dict) -> int:
        for field in description.get("fields", []):
            if field.get("name") == "embedding":
                params = field.get("params") or field.get("type_params") or {}
                return int(params.get("dim", 0))
        return 0

    def collection(self) -> tuple[MilvusClient, str]:
        client = self.connect()
        name = self.model_config.vector_collection
        with self._lock:
            if not client.has_collection(collection_name=name):
                schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
                schema.add_field(field_name="id", datatype=DataType.VARCHAR, max_length=64, is_primary=True)
                schema.add_field(field_name="chunk_id", datatype=DataType.INT64)
                schema.add_field(field_name="course_id", datatype=DataType.INT64)
                schema.add_field(field_name="document_id", datatype=DataType.INT64)
                schema.add_field(field_name="category", datatype=DataType.VARCHAR, max_length=80)
                schema.add_field(field_name="content_hash", datatype=DataType.VARCHAR, max_length=64)
                schema.add_field(
                    field_name="embedding", datatype=DataType.FLOAT_VECTOR,
                    dim=self.model_config.embedding_dimension,
                )
                index_params = client.prepare_index_params()
                index_params.add_index(
                    field_name="embedding", index_type="HNSW", metric_type="COSINE",
                    params={"M": 16, "efConstruction": 200},
                )
                client.create_collection(collection_name=name, schema=schema, index_params=index_params)
            else:
                actual_dimension = self._embedding_dimension(
                    client.describe_collection(collection_name=name)
                )
                if actual_dimension != self.model_config.embedding_dimension:
                    raise AppError(
                        "MILVUS_DIMENSION_MISMATCH",
                        f"collection {name} 的维度为 {actual_dimension}，当前 Embedding 配置为 "
                        f"{self.model_config.embedding_dimension}；请使用新的 collection 名称或重建向量索引",
                        409,
                    )
        client.load_collection(collection_name=name)
        return client, name

    def upsert(self, rows: list[dict]) -> None:
        if not rows:
            return
        client, name = self.collection()
        data = [{
            "id": str(row["chunk_id"]), "chunk_id": row["chunk_id"],
            "course_id": row["course_id"], "document_id": row["document_id"],
            "category": row["category"], "content_hash": row["content_hash"],
            "embedding": row["embedding"],
        } for row in rows]
        client.upsert(collection_name=name, data=data)
        client.flush(collection_name=name)

    def search(self, embedding: list[float], course_id: int, top_k: int) -> list[tuple[int, float]]:
        client, name = self.collection()
        results = client.search(
            collection_name=name, data=[embedding], anns_field="embedding",
            search_params={"metric_type": "COSINE", "params": {"ef": max(64, top_k * 4)}},
            limit=top_k, filter=f"course_id == {int(course_id)}", output_fields=["chunk_id"],
        )
        hits = results[0] if results else []
        return [
            (int((hit.get("entity") or {}).get("chunk_id")), float(hit.get("distance", hit.get("score", 0))))
            for hit in hits
        ]

    def delete_document(self, document_id: int) -> None:
        client, name = self.collection()
        client.delete(collection_name=name, filter=f"document_id == {int(document_id)}")
        client.flush(collection_name=name)

    def health(self) -> dict:
        client = self.connect()
        return {
            "ok": True, "collection": self.model_config.vector_collection,
            "dimension": self.model_config.embedding_dimension,
            "collections": client.list_collections(),
        }
