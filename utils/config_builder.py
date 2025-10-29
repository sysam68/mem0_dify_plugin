"""Build Mem0 local configuration from provider credentials.

This module parses simplified JSON blocks for local mode:
- local_llm_json
- local_embedder_json
- local_reranker_json (optional)
- local_vector_db_json
- local_graph_db_json (optional)

Each is expected to be a JSON object with at least {"provider": ..., "config": {...}}.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote_plus


class ConfigError(ValueError):
    pass


def _parse_json_block(raw: str | None, field_name: str) -> dict[str, Any] | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        raise ConfigError(f"{field_name} is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"{field_name} must be a JSON object")
    provider = data.get("provider")
    cfg = data.get("config")
    if not provider or not isinstance(cfg, dict):
        raise ConfigError(f"{field_name} must include 'provider' and 'config' object")
    return data


def _normalize_pgvector_config(config: dict[str, Any]) -> dict[str, Any]:
    """Normalize pgvector config to use a single connection_string if needed.

    Supports two forms:
    - Direct: {"connection_string": "postgresql://user:pass@host:port/dbname?sslmode=..."}
    - Discrete: {"dbname": ..., "user": ..., "password": ..., "host": ..., "port": ..., "sslmode": ...}
    """
    # If a usable connection string is already provided, keep it
    if "connection_string" in config and isinstance(config["connection_string"], str):
        return config

    dbname = config.get("dbname") or config.get("database") or ""
    user = config.get("user") or ""
    password = config.get("password") or ""
    host = config.get("host") or "localhost"
    port = str(config.get("port") or "5432")
    sslmode = config.get("sslmode")  # e.g., "disable" | "require"

    if not dbname or not user:
        # If insufficient fields, return as-is; Mem0 may handle other forms.
        return config

    user_enc = quote_plus(str(user))
    pwd_enc = quote_plus(str(password))
    # psycopg2 accepts postgresql:// URI; do NOT include '+psycopg2'
    dsn = f"postgresql://{user_enc}:{pwd_enc}@{host}:{port}/{dbname}"
    if sslmode:
        dsn = f"{dsn}?sslmode={quote_plus(str(sslmode))}"

    normalized: dict[str, Any] = {"connection_string": dsn}
    # Preserve optional tuning keys if present
    for key in ("collection_name", "embedding_model_dims", "metric"):
        if key in config and config[key] is not None:
            normalized[key] = config[key]
    return normalized


def build_local_mem0_config(credentials: dict[str, Any]) -> dict[str, Any]:
    """Construct mem0 local config dict from simplified JSON credential blocks.

    Required: local_llm_json, local_embedder_json, local_vector_db_json
    Optional: local_reranker_json, local_graph_db_json
    """
    llm = _parse_json_block(credentials.get("local_llm_json"), "local_llm_json")
    embedder = _parse_json_block(credentials.get("local_embedder_json"), "local_embedder_json")
    vector_store = _parse_json_block(credentials.get("local_vector_db_json"), "local_vector_db_json")

    if llm is None:
        raise ConfigError("LLM configuration (local_llm_json) is required in Local mode")
    if embedder is None:
        raise ConfigError("Embedder configuration (local_embedder_json) is required in Local mode")
    if vector_store is None:
        raise ConfigError("Vector Database configuration (local_vector_db_json) is required in Local mode")

    # Normalize pgvector config shape if necessary
    if (vector_store.get("provider") == "pgvector" and isinstance(vector_store.get("config"), dict)):
        vector_store["config"] = _normalize_pgvector_config(vector_store["config"])  # type: ignore[index]

    reranker = _parse_json_block(credentials.get("local_reranker_json"), "local_reranker_json")
    graph_store = _parse_json_block(credentials.get("local_graph_db_json"), "local_graph_db_json")

    config: dict[str, Any] = {
        "llm": llm,
        "embedder": embedder,
        "vector_store": vector_store,
    }
    if reranker:
        config["reranker"] = reranker
    if graph_store:
        config["graph_store"] = graph_store

    return config
