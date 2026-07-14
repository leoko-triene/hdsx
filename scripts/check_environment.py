import importlib.util
import json
import os
import socket
import sys
from pathlib import Path

import httpx


def tcp(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1): return True
    except OSError: return False


def main() -> int:
    packages = ["fastapi", "sqlalchemy", "alembic", "pymysql", "pytest", "pymilvus"]
    result = {
        "python": sys.version,
        "expected_env": "llm_learn",
        "conda_default_env": os.getenv("CONDA_DEFAULT_ENV"),
        "packages": {name: bool(importlib.util.find_spec(name)) for name in packages},
        "services": {"mysql:3306": tcp("127.0.0.1", 3306), "milvus:19530": tcp("127.0.0.1", 19530), "ollama:11434": tcp("127.0.0.1", 11434)},
        "models": {
            "qwen_transformers": Path(r"D:\transformers-models\Qwen2-0.5B").exists(),
            "reranker": Path(r"D:\class\Season4_5\code\homework1\models\bge-reranker-v2-m3").exists(),
        },
    }
    if result["services"]["ollama:11434"]:
        try: result["ollama_models"] = [m["name"] for m in httpx.get("http://127.0.0.1:11434/api/tags", timeout=3).json().get("models", [])]
        except Exception as exc: result["ollama_error"] = str(exc)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(result["packages"].values()) else 1


if __name__ == "__main__": raise SystemExit(main())

