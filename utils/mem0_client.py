"""Client adapters for Mem0 SaaS and local modes."""

from __future__ import annotations

import json
from typing import Any

from mem0 import Memory, MemoryClient

from .config_builder import build_local_mem0_config


def _normalize_search_results(results: object) -> list[dict[str, Any]]:
    """Normalize Mem0 search results into a list of dicts."""
    normalized: list[dict[str, Any]] = []
    if not results:
        return normalized

    items = results
    if isinstance(results, dict) and "results" in results:
        items = results["results"]

    for r in items or []:
        if not isinstance(r, dict):
            continue
        normalized.append(
            {
                "id": r.get("id") or r.get("memory_id") or "",
                "memory": r.get("memory") or r.get("text") or "",
                "score": r.get("score") or r.get("similarity", 0.0),
                "categories": r.get("categories") or [],
                "created_at": r.get("created_at") or r.get("timestamp") or "",
            },
        )
    return normalized


class SaaSClient:
    """Thin wrapper around Mem0 SaaS client."""

    def __init__(self, api_key: str) -> None:
        self._client = MemoryClient(api_key=api_key)

    def _build_filters(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        and_filters: list[dict[str, Any]] = []
        if payload.get("user_id"):
            and_filters.append({"user_id": payload["user_id"]})
        if payload.get("agent_id"):
            and_filters.append({"agent_id": payload["agent_id"]})
        if payload.get("run_id"):
            and_filters.append({"run_id": payload["run_id"]})
        return {"AND": and_filters} if and_filters else None

    def search(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        query = payload.get("query", "")
        filters = self._build_filters(payload)
        limit = payload.get("limit")
        # Pass limit to SDK if provided
        if limit is not None:
            results = self._client.search(query, filters=filters, limit=limit)
        else:
            results = self._client.search(query, filters=filters)
        normalized = _normalize_search_results(results)
        # Safeguard slicing in case backend ignores limit
        try:
            lim = int(limit) if limit is not None else None
        except (TypeError, ValueError):
            lim = None
        return normalized[:lim] if lim and lim > 0 else normalized

    def add(self, payload: dict[str, Any]) -> dict[str, Any]:
        metadata = payload.get("metadata")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = None

        # Build kwargs only with provided fields
        kwargs: dict[str, Any] = {}
        if payload.get("version"):
            kwargs["version"] = payload.get("version")
        if payload.get("user_id"):
            kwargs["user_id"] = payload.get("user_id")
        if payload.get("agent_id"):
            kwargs["agent_id"] = payload.get("agent_id")
        if payload.get("run_id"):
            kwargs["run_id"] = payload.get("run_id")
        if payload.get("app_id") is not None:
            kwargs["app_id"] = payload.get("app_id")
        if metadata is not None:
            kwargs["metadata"] = metadata
        if payload.get("output_format"):
            kwargs["output_format"] = payload.get("output_format")

        # Use messages directly if provided; otherwise fall back to a single string
        first_arg = payload.get("messages")
        if first_arg is None:
            first_arg = payload.get("user") or ""

        return self._client.add(first_arg, **kwargs)

    def get_all(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        filters = self._build_filters(params)
        results = self._client.get_all(version="v2", filters=filters)
        return results or []

    def get(self, memory_id: str) -> dict[str, Any]:
        return self._client.get(memory_id)

    def update(self, memory_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._client.update(memory_id, payload.get("text"))

    def delete(self, memory_id: str) -> dict[str, Any]:
        return self._client.delete(memory_id)

    def delete_all(self, params: dict[str, Any]) -> dict[str, Any]:
        filters = self._build_filters(params)
        return self._client.delete_all(version="v2", filters=filters)

    def history(self, memory_id: str) -> list[dict[str, Any]]:
        return self._client.history(memory_id)


class LocalClient:
    """Local Mem0 client using configured providers."""

    def __init__(self, credentials: dict[str, Any]) -> None:
        config = build_local_mem0_config(credentials)
        self._memory = Memory.from_config(config)

    def search(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        query = payload.get("query", "")
        version = payload.get("version")
        filters = payload.get("filters")
        limit = payload.get("limit")
        # Pass limit to local search when available; otherwise slice later
        if version == "v2" and isinstance(filters, dict):
            if limit is not None:
                results = self._memory.search(query, filters=filters, limit=limit)
            else:
                results = self._memory.search(query, filters=filters)
        elif limit is not None:
            results = self._memory.search(
                query,
                user_id=payload.get("user_id"),
                agent_id=payload.get("agent_id"),
                run_id=payload.get("run_id"),
                limit=limit,
            )
        else:
            results = self._memory.search(
                query,
                user_id=payload.get("user_id"),
                agent_id=payload.get("agent_id"),
                run_id=payload.get("run_id"),
            )
        normalized = _normalize_search_results(results)
        try:
            lim = int(limit) if limit is not None else None
        except (TypeError, ValueError):
            lim = None
        return normalized[:lim] if lim and lim > 0 else normalized

    def add(self, payload: dict[str, Any]) -> dict[str, Any]:
        metadata = payload.get("metadata")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = None

        # Build kwargs only with provided fields (ignore app_id in local)
        kwargs: dict[str, Any] = {}
        if payload.get("user_id"):
            kwargs["user_id"] = payload.get("user_id")
        if payload.get("agent_id"):
            kwargs["agent_id"] = payload.get("agent_id")
        if payload.get("run_id"):
            kwargs["run_id"] = payload.get("run_id")
        if metadata is not None:
            kwargs["metadata"] = metadata

        # Use messages directly if provided; otherwise fall back to a single string
        first_arg = payload.get("messages")
        if first_arg is None:
            first_arg = payload.get("user") or ""

        return self._memory.add(first_arg, **kwargs)

    def get_all(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        version = params.get("version")
        filters = params.get("filters")
        if version == "v2" and isinstance(filters, dict):
            results = self._memory.get_all(version="v2", filters=filters)
        else:
            results = self._memory.get_all(
                user_id=params.get("user_id"),
                agent_id=params.get("agent_id"),
                run_id=params.get("run_id"),
            )
        return results or []

    def get(self, memory_id: str) -> dict[str, Any]:
        return self._memory.get(memory_id)

    def update(self, memory_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._memory.update(memory_id, payload.get("text"))

    def delete(self, memory_id: str) -> dict[str, Any]:
        return self._memory.delete(memory_id)

    def delete_all(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._memory.delete_all(
            user_id=params.get("user_id"),
            agent_id=params.get("agent_id"),
            run_id=params.get("run_id"),
        )

    def history(self, memory_id: str) -> list[dict[str, Any]]:
        return self._memory.history(memory_id)


def get_mem0_client(credentials: dict[str, Any]) -> SaaSClient | LocalClient:
    mode_raw = credentials.get("mode") or "SaaS"
    mode = str(mode_raw).strip().lower()
    if mode == "saas":
        api_key = credentials.get("mem0_api_key")
        if not api_key:
            msg = "mem0_api_key is required for SaaS mode"
            raise ValueError(msg)
        return SaaSClient(api_key)
    return LocalClient(credentials)
