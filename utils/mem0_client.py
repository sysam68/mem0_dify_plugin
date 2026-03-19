"""Client adapter for Mem0 local mode only."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import inspect
import json
import threading
import traceback
from datetime import date, datetime, timezone
from typing import Any

import mem0.memory.main as mem0_main
from mem0 import AsyncMemory, Memory

from .config_builder import build_local_mem0_config
from .constants import ADD_SKIP_RESULT, CUSTOM_PROMPT, MAX_CONCURRENT_MEMORY_OPERATIONS
from .logger import format_exception, get_logger

logger = get_logger(__name__)

EXPIRATION_DATE_KEY = "expiration_date"


def _normalize_tool_calls_response(response: Any) -> Any:
    """Decode tool call arguments when returned as JSON strings."""
    if not isinstance(response, dict):
        return response
    tool_calls = response.get("tool_calls")
    if not isinstance(tool_calls, list):
        return response
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        args_obj = call.get("arguments")
        if args_obj is None and isinstance(call.get("function"), dict):
            args_obj = call["function"].get("arguments")
        if isinstance(args_obj, str):
            try:
                args_obj = json.loads(args_obj)
                call["arguments"] = args_obj
            except Exception:
                continue
        if isinstance(args_obj, dict):
            for key in ("entities", "relations"):
                val = args_obj.get(key)
                if isinstance(val, str):
                    try:
                        args_obj[key] = json.loads(val)
                    except Exception:
                        continue
    return response


def _strip_additional_properties(payload: Any) -> Any:
    """Recursively drop JSON Schema additionalProperties entries for Ollama /v1."""
    if isinstance(payload, dict):
        return {
            key: _strip_additional_properties(value)
            for key, value in payload.items()
            if key != "additionalProperties"
        }
    if isinstance(payload, list):
        return [_strip_additional_properties(item) for item in payload]
    return payload


def _patch_graph_llm(memory_obj: Any) -> None:
    """Patch graph LLM to normalize tool call payloads from Ollama/OpenAI."""
    graph = getattr(memory_obj, "graph", None)
    llm = getattr(graph, "llm", None)
    generate = getattr(llm, "generate_response", None)
    if not callable(generate):
        return
    if getattr(generate, "_mem0_dify_tool_patch", False):
        return

    def patched_generate_response(*args, **kwargs):
        if "tools" in kwargs and kwargs["tools"]:
            kwargs = dict(kwargs)
            kwargs["tools"] = _strip_additional_properties(kwargs["tools"])
        response = generate(*args, **kwargs)
        return _normalize_tool_calls_response(response)

    patched_generate_response._mem0_dify_tool_patch = True  # type: ignore[attr-defined]
    llm.generate_response = patched_generate_response


def _patch_neo4j_graph_token() -> None:
    """Patch langchain_neo4j to avoid token/database positional mismatch."""
    try:
        from langchain_neo4j.graphs.neo4j_graph import Neo4jGraph
    except Exception:
        return

    init = Neo4jGraph.__init__
    if getattr(init, "_mem0_dify_token_patch", False):
        return

    try:
        import inspect

        if "token" not in inspect.signature(init).parameters:
            return
    except Exception:
        return

    def patched_init(
        self,
        url=None,
        username=None,
        password=None,
        token=None,
        database=None,
        *args,
        **kwargs,
    ):
        if token is not None and database is None and username and password:
            database = token
            token = None
        return init(self, url, username, password, token, database, *args, **kwargs)

    patched_init._mem0_dify_token_patch = True  # type: ignore[attr-defined]
    Neo4jGraph.__init__ = patched_init
    logger.info("Patched Neo4jGraph to avoid token/db positional mismatch")


def _apply_project_settings(
    memory_obj: Any,
    enable_graph: bool,
    instructions: str | None,
) -> None:
    """Apply project-level settings (graph toggle, instructions) if supported."""
    if not enable_graph and not instructions:
        return
    try:
        project = getattr(memory_obj, "project", None)
        if project and hasattr(project, "update"):
            updates: dict[str, Any] = {}
            if enable_graph:
                updates["enable_graph"] = True
            if instructions:
                updates["custom_instructions"] = instructions
            if updates:
                project.update(**updates)
                logger.info("Applied project settings: %s", ", ".join(updates.keys()))
    except Exception:
        logger.exception("Failed to apply project settings at project level")


def _get_config_hash(credentials: dict[str, Any]) -> str:
    """Generate a hash from credentials for cache key.

    This function creates a hash of the credentials to detect configuration changes.
    The hash is used only for in-memory comparison and is never logged or included
    in exception messages to avoid exposing sensitive information.

    Security notes:
    - Uses SHA256 (one-way hash) - credentials cannot be recovered from the hash
    - Hash value is only stored in memory, never logged or printed
    - Hash includes all credential fields (including sensitive ones like api_key,
      password, token) but the hash itself is safe to use for comparison

    Args:
        credentials: Configuration dictionary (may contain sensitive fields like
            api_key, password, token, etc.).

    Returns:
        str: SHA256 hash of the serialized credentials (hex digest).

    """
    try:
        cred_str = json.dumps(credentials, sort_keys=True)
        return hashlib.sha256(cred_str.encode()).hexdigest()
    except Exception as e:
        # If serialization fails, log the error and return empty string to disable caching
        logger.exception(
            "Failed to generate config hash from credentials: %s",
            type(e).__name__,
        )
        return ""


# Module-level client instances and locks
_local_client: LocalClient | None = None
_local_client_config_hash: str | None = None
_local_client_lock = threading.Lock()

_async_client: AsyncLocalClient | None = None
_async_client_config_hash: str | None = None
_async_client_lock = threading.Lock()


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
        record = _promote_expiration_date(_copy_dict(r))
        if _is_expired_memory_record(record):
            continue

        normalized_record = {
            "id": record.get("id") or record.get("memory_id") or "",
            "memory": record.get("memory") or record.get("text") or "",
            "score": record.get("score") or record.get("similarity", 0.0),
            "metadata": record.get("metadata") or {},
            "created_at": record.get("created_at") or record.get("timestamp") or "",
        }
        if record.get(EXPIRATION_DATE_KEY):
            normalized_record[EXPIRATION_DATE_KEY] = record.get(EXPIRATION_DATE_KEY)
        normalized.append(normalized_record)
    return normalized


def _count_payload_messages(messages: Any) -> int:
    """Return the number of messages present in an add payload."""
    return len(messages) if isinstance(messages, (list, tuple)) else 0


def _message_shapes(messages: Any) -> list[str]:
    """Return a compact representation of the add-message payload shape."""
    if not isinstance(messages, (list, tuple)):
        return [type(messages).__name__]

    shapes: list[str] = []
    for item in messages:
        if isinstance(item, dict):
            shapes.append(f"dict({item.get('role', '-')})")
        else:
            shapes.append(type(item).__name__)
    return shapes


def _supports_expiration_argument(method: Any) -> bool:
    """Return True when the given add method supports expiration_date."""
    try:
        return EXPIRATION_DATE_KEY in inspect.signature(method).parameters
    except Exception:
        return False


def _copy_dict(value: Any) -> dict[str, Any]:
    """Return a shallow copy when value is a dict, else an empty dict."""
    return dict(value) if isinstance(value, dict) else {}


def _normalize_add_metadata(metadata: Any, *, user_id: str | None = None) -> dict[str, Any] | None:
    """Normalize metadata to a dict, dropping unsupported scalar/list shapes."""
    if metadata is None:
        return None

    parsed_metadata = metadata
    if isinstance(parsed_metadata, str):
        try:
            parsed_metadata = json.loads(parsed_metadata)
        except (TypeError, ValueError):
            logger.warning(
                "Ignoring metadata because it is not valid JSON object text (user_id: %s, metadata_type: %s)",
                user_id or "-",
                type(metadata).__name__,
            )
            return None

    if isinstance(parsed_metadata, dict):
        return dict(parsed_metadata)

    logger.warning(
        "Ignoring metadata because Mem0 add expects a JSON object (user_id: %s, metadata_type: %s)",
        user_id or "-",
        type(parsed_metadata).__name__,
    )
    return None


def _normalize_add_messages(messages: Any, *, user_id: str | None = None) -> Any:
    """Normalize add-message payloads to Mem0's expected list[dict] shape."""
    if isinstance(messages, str):
        return messages

    if isinstance(messages, dict):
        return messages

    if not isinstance(messages, (list, tuple)):
        return messages

    normalized: list[dict[str, Any]] = []
    skipped = 0
    converted = 0

    for item in messages:
        if isinstance(item, dict):
            role = item.get("role")
            content = item.get("content")
            if role is None or content is None:
                skipped += 1
                continue
            normalized.append(dict(item))
            continue

        if isinstance(item, str):
            text = item.strip()
            if text:
                normalized.append({"role": "user", "content": text})
                converted += 1
            else:
                skipped += 1
            continue

        skipped += 1

    if converted or skipped:
        logger.warning(
            "Normalized add-memory message payload before Mem0 call (user_id: %s, converted_strings: %d, skipped_items: %d, resulting_shapes: %s)",
            user_id or "-",
            converted,
            skipped,
            _message_shapes(normalized),
        )

    return normalized


def _safe_mem0_message_dicts(messages: Any) -> list[dict[str, Any]]:
    """Return only Mem0-compatible message dicts, converting raw strings when possible."""
    normalized = _normalize_add_messages(messages)
    if isinstance(normalized, dict):
        normalized = [normalized]
    if isinstance(normalized, str):
        normalized = [{"role": "user", "content": normalized}]
    if not isinstance(normalized, (list, tuple)):
        return []
    return [
        dict(item)
        for item in normalized
        if isinstance(item, dict) and item.get("role") is not None and item.get("content") is not None
    ]


def _safe_mem0_messages_to_text(messages: Any) -> str:
    """Build the text form Mem0 expects without failing on malformed items."""
    parts: list[str] = []
    for message in _safe_mem0_message_dicts(messages):
        role = message.get("role")
        content = message.get("content")
        if role in {"system", "user", "assistant"}:
            parts.append(f"{role}: {content}")
    return "\n".join(parts) + ("\n" if parts else "")


def _coerce_expiration_date(expiration_date: Any) -> str | None:
    """Normalize expiration_date values to strings for payload storage."""
    if expiration_date is None:
        return None
    if isinstance(expiration_date, datetime):
        return expiration_date.isoformat()
    if isinstance(expiration_date, date):
        return expiration_date.isoformat()
    if isinstance(expiration_date, str):
        value = expiration_date.strip()
        return value or None
    return str(expiration_date)


def _merge_expiration_metadata(
    metadata: dict[str, Any] | None,
    expiration_date: Any,
) -> dict[str, Any] | None:
    """Store expiration_date internally in the Mem0 payload metadata."""
    normalized_expiration = _coerce_expiration_date(expiration_date)
    if not normalized_expiration:
        return metadata

    merged = _copy_dict(metadata)
    merged[EXPIRATION_DATE_KEY] = normalized_expiration
    return merged


def _extract_expiration_date(record: dict[str, Any]) -> Any:
    """Return expiration_date from a normalized memory record."""
    if EXPIRATION_DATE_KEY in record:
        return record.get(EXPIRATION_DATE_KEY)
    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        return metadata.get(EXPIRATION_DATE_KEY)
    return None


def _parse_expiration_date(expiration_date: Any) -> tuple[date | None, datetime | None]:
    """Parse expiration_date values as ISO date or datetime."""
    if expiration_date is None:
        return None, None

    if isinstance(expiration_date, datetime):
        return None, expiration_date

    if isinstance(expiration_date, date):
        return expiration_date, None

    if not isinstance(expiration_date, str):
        return None, None

    value = expiration_date.strip()
    if not value:
        return None, None

    try:
        if "T" not in value and " " not in value and len(value) <= 10:
            return date.fromisoformat(value), None
    except ValueError:
        pass

    try:
        return None, datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None, None


def _is_expired_expiration_date(expiration_date: Any) -> bool:
    """Return True when the expiration date is in the past."""
    parsed_date, parsed_datetime = _parse_expiration_date(expiration_date)

    if parsed_datetime is not None:
        if parsed_datetime.tzinfo is None:
            parsed_datetime = parsed_datetime.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return now > parsed_datetime.astimezone(timezone.utc)

    if parsed_date is not None:
        return datetime.now(timezone.utc).date() > parsed_date

    return False


def _promote_expiration_date(record: dict[str, Any]) -> dict[str, Any]:
    """Promote expiration_date out of metadata for plugin-facing results."""
    promoted = _copy_dict(record)
    metadata = promoted.get("metadata")
    expiration_date = promoted.get(EXPIRATION_DATE_KEY)

    if isinstance(metadata, dict) and expiration_date is None:
        expiration_date = metadata.get(EXPIRATION_DATE_KEY)

    if isinstance(metadata, dict) and EXPIRATION_DATE_KEY in metadata:
        metadata = dict(metadata)
        metadata.pop(EXPIRATION_DATE_KEY, None)
        if metadata:
            promoted["metadata"] = metadata
        else:
            promoted.pop("metadata", None)

    if expiration_date is not None:
        promoted[EXPIRATION_DATE_KEY] = expiration_date

    return promoted


def _is_expired_memory_record(record: dict[str, Any]) -> bool:
    """Return True when a memory record contains an expired expiration_date."""
    return _is_expired_expiration_date(_extract_expiration_date(record))


def _filter_memory_results(results: Any) -> Any:
    """Promote expiration_date and drop expired memories from SDK results."""
    if isinstance(results, dict) and isinstance(results.get("results"), list):
        filtered = dict(results)
        filtered["results"] = [
            promoted
            for item in results["results"]
            if isinstance(item, dict)
            for promoted in [_promote_expiration_date(item)]
            if not _is_expired_memory_record(promoted)
        ]
        return filtered

    if isinstance(results, list):
        return [
            promoted
            for item in results
            if isinstance(item, dict)
            for promoted in [_promote_expiration_date(item)]
            if not _is_expired_memory_record(promoted)
        ]

    if isinstance(results, dict):
        promoted = _promote_expiration_date(results)
        if _is_expired_memory_record(promoted):
            return None
        return promoted

    return results


def _patch_sync_add_expiration() -> None:
    """Patch local sync Memory.add when installed SDK lacks expiration_date support."""
    original_add = Memory.add
    if getattr(original_add, "_mem0_dify_expiration_patch", False):
        return
    if _supports_expiration_argument(original_add):
        return

    def patched_add(
        self,
        messages,
        *,
        user_id=None,
        agent_id=None,
        run_id=None,
        metadata=None,
        infer=True,
        memory_type=None,
        prompt=None,
        expiration_date=None,
    ):
        merged_metadata = _merge_expiration_metadata(metadata, expiration_date)
        return original_add(
            self,
            messages,
            user_id=user_id,
            agent_id=agent_id,
            run_id=run_id,
            metadata=merged_metadata,
            infer=infer,
            memory_type=memory_type,
            prompt=prompt,
        )

    patched_add._mem0_dify_expiration_patch = True  # type: ignore[attr-defined]
    Memory.add = patched_add
    logger.info(
        "Patched local Memory.add to support expiration_date via plugin compatibility layer",
    )


def _patch_async_add_expiration() -> None:
    """Patch local async AsyncMemory.add when installed SDK lacks expiration_date support."""
    original_add = AsyncMemory.add
    if getattr(original_add, "_mem0_dify_expiration_patch", False):
        return
    if _supports_expiration_argument(original_add):
        return

    async def patched_add(
        self,
        messages,
        *,
        user_id=None,
        agent_id=None,
        run_id=None,
        metadata=None,
        infer=True,
        memory_type=None,
        prompt=None,
        llm=None,
        expiration_date=None,
    ):
        merged_metadata = _merge_expiration_metadata(metadata, expiration_date)
        return await original_add(
            self,
            messages,
            user_id=user_id,
            agent_id=agent_id,
            run_id=run_id,
            metadata=merged_metadata,
            infer=infer,
            memory_type=memory_type,
            prompt=prompt,
            llm=llm,
        )

    patched_add._mem0_dify_expiration_patch = True  # type: ignore[attr-defined]
    AsyncMemory.add = patched_add
    logger.info(
        "Patched local AsyncMemory.add to support expiration_date via plugin compatibility layer",
    )


def _patch_sync_update_expiration() -> None:
    """Preserve expiration_date when local Memory.update rewrites payload metadata."""
    original_update_memory = Memory._update_memory
    if getattr(original_update_memory, "_mem0_dify_expiration_patch", False):
        return

    def patched_update_memory(self, memory_id, data, existing_embeddings, metadata=None):
        merged_metadata = _copy_dict(metadata)
        if EXPIRATION_DATE_KEY not in merged_metadata:
            with contextlib.suppress(Exception):
                existing_memory = self.vector_store.get(vector_id=memory_id)
                if existing_memory and getattr(existing_memory, "payload", None):
                    expiration_date = existing_memory.payload.get(EXPIRATION_DATE_KEY)
                    if expiration_date is not None:
                        merged_metadata[EXPIRATION_DATE_KEY] = expiration_date
        return original_update_memory(
            self,
            memory_id,
            data,
            existing_embeddings,
            metadata=merged_metadata or None,
        )

    patched_update_memory._mem0_dify_expiration_patch = True  # type: ignore[attr-defined]
    Memory._update_memory = patched_update_memory


def _patch_async_update_expiration() -> None:
    """Preserve expiration_date when local AsyncMemory.update rewrites payload metadata."""
    original_update_memory = AsyncMemory._update_memory
    if getattr(original_update_memory, "_mem0_dify_expiration_patch", False):
        return

    async def patched_update_memory(self, memory_id, data, existing_embeddings, metadata=None):
        merged_metadata = _copy_dict(metadata)
        if EXPIRATION_DATE_KEY not in merged_metadata:
            with contextlib.suppress(Exception):
                existing_memory = await asyncio.to_thread(self.vector_store.get, vector_id=memory_id)
                if existing_memory and getattr(existing_memory, "payload", None):
                    expiration_date = existing_memory.payload.get(EXPIRATION_DATE_KEY)
                    if expiration_date is not None:
                        merged_metadata[EXPIRATION_DATE_KEY] = expiration_date
        return await original_update_memory(
            self,
            memory_id,
            data,
            existing_embeddings,
            metadata=merged_metadata or None,
        )

    patched_update_memory._mem0_dify_expiration_patch = True  # type: ignore[attr-defined]
    AsyncMemory._update_memory = patched_update_memory


def _patch_sync_read_expiration() -> None:
    """Patch sync read methods to promote and filter expiration_date."""
    for method_name in ("get", "get_all", "search"):
        original_method = getattr(Memory, method_name)
        if getattr(original_method, "_mem0_dify_expiration_patch", False):
            continue

        def _make_patched(method):
            def patched(*args, **kwargs):
                return _filter_memory_results(method(*args, **kwargs))

            patched._mem0_dify_expiration_patch = True  # type: ignore[attr-defined]
            return patched

        setattr(Memory, method_name, _make_patched(original_method))


def _patch_async_read_expiration() -> None:
    """Patch async read methods to promote and filter expiration_date."""
    for method_name in ("get", "get_all", "search"):
        original_method = getattr(AsyncMemory, method_name)
        if getattr(original_method, "_mem0_dify_expiration_patch", False):
            continue

        def _make_patched(method):
            async def patched(*args, **kwargs):
                return _filter_memory_results(await method(*args, **kwargs))

            patched._mem0_dify_expiration_patch = True  # type: ignore[attr-defined]
            return patched

        setattr(AsyncMemory, method_name, _make_patched(original_method))


def _patch_local_mem0_expiration() -> None:
    """Enable plugin-level expiration_date support for local Mem0 classes."""
    _patch_sync_add_expiration()
    _patch_async_add_expiration()
    _patch_sync_update_expiration()
    _patch_async_update_expiration()
    _patch_sync_read_expiration()
    _patch_async_read_expiration()


def _patch_mem0_message_handling() -> None:
    """Make Mem0 message parsing and graph add resilient to malformed items."""
    parse_messages = getattr(mem0_main, "parse_messages", None)
    if callable(parse_messages) and not getattr(parse_messages, "_mem0_dify_safe_patch", False):
        def patched_parse_messages(messages):
            return _safe_mem0_messages_to_text(messages)

        patched_parse_messages._mem0_dify_safe_patch = True  # type: ignore[attr-defined]
        mem0_main.parse_messages = patched_parse_messages

    for cls in (Memory, AsyncMemory):
        original_should_use = getattr(cls, "_should_use_agent_memory_extraction")
        if not getattr(original_should_use, "_mem0_dify_safe_patch", False):
            def _make_should_use(method):
                def patched(self, messages, metadata):
                    safe_messages = _safe_mem0_message_dicts(messages)
                    safe_metadata = metadata if isinstance(metadata, dict) else {}
                    return method(self, safe_messages, safe_metadata)

                patched._mem0_dify_safe_patch = True  # type: ignore[attr-defined]
                return patched

            setattr(cls, "_should_use_agent_memory_extraction", _make_should_use(original_should_use))

    original_sync_add_to_graph = Memory._add_to_graph
    if not getattr(original_sync_add_to_graph, "_mem0_dify_safe_patch", False):
        def patched_sync_add_to_graph(self, messages, filters):
            return original_sync_add_to_graph(self, _safe_mem0_message_dicts(messages), filters)

        patched_sync_add_to_graph._mem0_dify_safe_patch = True  # type: ignore[attr-defined]
        Memory._add_to_graph = patched_sync_add_to_graph

    original_async_add_to_graph = AsyncMemory._add_to_graph
    if not getattr(original_async_add_to_graph, "_mem0_dify_safe_patch", False):
        async def patched_async_add_to_graph(self, messages, filters):
            return await original_async_add_to_graph(self, _safe_mem0_message_dicts(messages), filters)

        patched_async_add_to_graph._mem0_dify_safe_patch = True  # type: ignore[attr-defined]
        AsyncMemory._add_to_graph = patched_async_add_to_graph


_patch_local_mem0_expiration()
_patch_mem0_message_handling()
_SYNC_ADD_SUPPORTS_EXPIRATION = _supports_expiration_argument(Memory.add)
_ASYNC_ADD_SUPPORTS_EXPIRATION = _supports_expiration_argument(AsyncMemory.add)


class LocalClient:
    """Local Mem0 client using configured providers."""

    def __init__(self, credentials: dict[str, Any]) -> None:
        """Initialize the LocalClient.

        Args:
            credentials (dict): Configuration for the LocalClient.

        """
        logger.info("Initializing LocalClient")
        _patch_neo4j_graph_token()
        config = build_local_mem0_config(credentials)
        self.enable_graph = bool(config.get("enable_graph"))
        self.custom_instructions = config.get("custom_instructions")
        self.memory = Memory.from_config(config)
        _apply_project_settings(self.memory, self.enable_graph, self.custom_instructions)
        _patch_graph_llm(self.memory)
        self.use_custom_prompt = True
        self.custom_prompt = CUSTOM_PROMPT
        logger.info("LocalClient initialized successfully")

    def search(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Search for memories based on a query.

        Args:
            payload (dict): Search parameters. Supported keys:
                - query (str): Query to search for.
                - user_id (str, optional): ID of the user.
                - agent_id (str, optional): ID of the agent.
                - run_id (str, optional): ID of the run.
                - limit (int, optional): Max number of results.
                - filters (dict, optional): Metadata filters, supporting:
                    * {"key": "value"} (exact match)
                    * {"key": {"eq"/"ne"/"in"/"nin"/"gt"/"gte"/"lt"/"lte"/"contains"/"icontains"}: ...}
                    * {"key": "*"} (wildcard)
                    * {"AND"/"OR"/"NOT": [filters,...]} (logic ops)
                - threshold (float, optional): Minimum score (not used in local mode).

        Returns:
            list[dict]: List of memory search results.

        """  # noqa: E501
        query = payload.get("query", "")
        filters = payload.get("filters")
        limit = payload.get("limit")

        # Normalize limit to int when possible
        try:
            lim = int(limit) if limit is not None else None
        except (TypeError, ValueError):
            lim = None

        # Build kwargs with non-empty args to simplify branching
        kwargs: dict[str, Any] = {}
        if lim is not None:
            kwargs["limit"] = lim
        if isinstance(filters, dict):
            kwargs["filters"] = filters
        else:
            if payload.get("user_id"):
                kwargs["user_id"] = payload.get("user_id")
            if payload.get("agent_id"):
                kwargs["agent_id"] = payload.get("agent_id")
            if payload.get("run_id"):
                kwargs["run_id"] = payload.get("run_id")

        try:
            results = self.memory.search(query, **kwargs)
            normalized = _normalize_search_results(results)
        except Exception:
            logger.exception("Error during memory search")
            raise
        else:
            return normalized

    def add(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a new memory.

        Adds new memories scoped to a single session id (e.g. user_id, agent_id, or run_id).
        One of those ids is required.

        Args:
            payload (dict): A dictionary containing all parameters for adding a memory, including:
                - messages (str or list[dict[str, str]]): The message content or list of messages
                  (e.g., [{"role": "user", "content": "Hello"}, ...]) to process and store.
                - user_id (str, optional): ID of the user creating the memory.
                - agent_id (str, optional): ID of the agent creating the memory.
                - run_id (str, optional): ID of the run creating the memory.
                - metadata (dict or str, optional): Metadata to store with the memory.
                  Can be a dict or a JSON string.
                - infer (bool, optional): If True (default), uses LLM to extract key facts
                  and manage memories.
                - memory_type (str, optional): Type of memory. Defaults to conversational or factual.
                  Use "procedural_memory" for procedural type.
                - prompt (str, optional): Custom prompt to use for memory creation.
                - expiration_date (str, optional): Expiration date/TTL (e.g., YYYY-MM-DD or ISO string),
                  only when supported by the installed local Mem0 SDK.

        Returns:
            dict: Result of the memory addition, typically with items added/updated (in "results"),
            and possibly "relations" if graph store is enabled.

        """  # noqa: E501
        metadata = _normalize_add_metadata(payload.get("metadata"), user_id=payload.get("user_id"))
        messages = _normalize_add_messages(payload.get("messages"), user_id=payload.get("user_id"))

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
        expiration_date = payload.get("expiration_date")
        if expiration_date and _SYNC_ADD_SUPPORTS_EXPIRATION:
            kwargs["expiration_date"] = expiration_date
        elif expiration_date:
            logger.warning(
                "Ignoring expiration_date for sync Mem0 client because installed Memory.add does not support it (user_id: %s, requested_expiration_date: %s)",
                payload.get("user_id") or "-",
                expiration_date,
            )
        if self.use_custom_prompt:
            kwargs["prompt"] = self.custom_prompt

        try:
            result = self.memory.add(messages, **kwargs)
        except Exception as error:
            traceback_text = "".join(
                traceback.format_exception(type(error), error, error.__traceback__),
            ).strip()
            logger.error(
                "Memory addition failed in sync Mem0 client (user_id: %s, agent_id: %s, run_id: %s, message_count: %d, message_shapes: %s, metadata_present: %s, expiration_date: %s): %s",
                payload.get("user_id") or "-",
                payload.get("agent_id") or "-",
                payload.get("run_id") or "-",
                _count_payload_messages(messages),
                _message_shapes(messages),
                metadata is not None,
                expiration_date or "-",
                format_exception(error),
            )
            if traceback_text:
                logger.error("Sync Mem0 add traceback (user_id: %s):\n%s", payload.get("user_id") or "-", traceback_text)
            logger.debug(
                "Stack trace for sync Mem0 memory addition failure",
                exc_info=(type(error), error, error.__traceback__),
            )
            raise
        else:
            return result

    def get_all(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Get all memories based on user/agent/run identifiers with optional filters.

        Args:
            params (dict): Parameters including:
                - user_id (str, optional): User ID to filter by.
                - agent_id (str, optional): Agent ID to filter by.
                - run_id (str, optional): Run ID to filter by.
                - limit (int, optional): Maximum number of results to return.
                - filters (dict, optional): Advanced metadata filters.

        Returns:
            list[dict]: List of memory objects.

        """
        # Build kwargs with all provided parameters
        kwargs: dict[str, Any] = {}

        # Add entity IDs if provided
        if params.get("user_id"):
            kwargs["user_id"] = params.get("user_id")
        if params.get("agent_id"):
            kwargs["agent_id"] = params.get("agent_id")
        if params.get("run_id"):
            kwargs["run_id"] = params.get("run_id")

        # Add optional parameters
        limit = params.get("limit")
        if limit is not None:
            with contextlib.suppress(TypeError, ValueError):
                kwargs["limit"] = int(limit)

        filters = params.get("filters")
        if isinstance(filters, dict):
            kwargs["filters"] = filters

        # Mem0's get_all always returns {"results": [...]} format
        try:
            result = self.memory.get_all(**kwargs)
            memories = result.get("results", []) if isinstance(result, dict) else []
        except Exception:
            logger.exception("Error during get_all operation")
            raise
        else:
            return memories

    def get(self, memory_id: str) -> dict[str, Any]:
        """Get a single memory by ID.

        Args:
            memory_id (str): The ID of the memory to retrieve.

        Returns:
            dict: Memory object with id, memory, metadata, created_at, updated_at, etc.

        """
        try:
            result = self.memory.get(memory_id)
        except Exception:
            logger.exception("Error retrieving memory %s", memory_id)
            raise
        else:
            return result

    def update(self, memory_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update a memory by ID.

        Args:
            memory_id (str): ID of the memory to update.
            payload (dict): Dictionary containing new content under the "text" key.

        Returns:
            dict: Success message indicating the memory was updated.

        """
        try:
            result = self.memory.update(memory_id, payload.get("text"))
        except Exception:
            logger.exception("Error updating memory %s", memory_id)
            raise
        else:
            return result

    def delete(self, memory_id: str) -> dict[str, Any]:
        """Delete a memory by ID.

        Args:
            memory_id (str): The ID of the memory to delete.

        Returns:
            dict: Success message, typically {"message": "Memory deleted successfully!"}.

        """
        try:
            result = self.memory.delete(memory_id)
        except Exception:
            logger.exception("Error deleting memory %s", memory_id)
            raise
        else:
            return result

    def delete_all(self, params: dict[str, Any]) -> dict[str, Any]:
        """Delete all memories matching the given filters.

        Args:
            params (dict): Parameters including:
                - user_id (str, optional): User ID to filter by.
                - agent_id (str, optional): Agent ID to filter by.
                - run_id (str, optional): Run ID to filter by.

        Returns:
            dict: Result of the deletion operation.

        """
        try:
            result = self.memory.delete_all(
                user_id=params.get("user_id"),
                agent_id=params.get("agent_id"),
                run_id=params.get("run_id"),
            )
        except Exception:
            logger.exception("Error during delete_all operation")
            raise
        else:
            return result

    def history(self, memory_id: str) -> list[dict[str, Any]]:
        """Get the history of changes for a specific memory.

        Args:
            memory_id (str): The ID of the memory to get history for.

        Returns:
            list[dict]: List of history records with old_memory, new_memory, event, created_at, etc.

        """
        try:
            result = self.memory.history(memory_id)
        except Exception:
            logger.exception("Error retrieving history for memory %s", memory_id)
            raise
        else:
            return result


class AsyncLocalClient:
    """Async local Mem0 client using configured providers."""

    def __init__(self, credentials: dict[str, Any]) -> None:
        """Initialize the AsyncLocalClient.

        Args:
            credentials (dict): Configuration for the AsyncLocalClient.

        """
        logger.info("Initializing AsyncLocalClient")
        self.config = build_local_mem0_config(credentials)
        self.enable_graph = bool(self.config.get("enable_graph"))
        self.custom_instructions = self.config.get("custom_instructions")
        self.memory = None
        # Async lock to protect one-time asynchronous initialization.
        self._create_lock = asyncio.Lock()
        # Semaphore to limit the concurrency of memory operations
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_MEMORY_OPERATIONS)
        # Toggle whether to use custom prompt
        self.use_custom_prompt = True
        self.custom_prompt = CUSTOM_PROMPT
        logger.info("AsyncLocalClient initialized successfully")

    async def create(self) -> AsyncMemory:
        """Lazily create AsyncMemory once."""
        if self.memory is not None:
            return self.memory
        async with self._create_lock:
            if self.memory is None:
                logger.info("Creating AsyncMemory instance")
                _patch_neo4j_graph_token()
                self.memory = await AsyncMemory.from_config(self.config)
                _apply_project_settings(self.memory, self.enable_graph, self.custom_instructions)
                _patch_graph_llm(self.memory)
                logger.info("AsyncMemory instance created successfully")
        return self.memory

    async def aclose(self) -> None:
        """Close and cleanup resources held by AsyncMemory.

        Mem0's resources (PGVector, SQLiteManager, etc.) all implement __del__
        methods that automatically clean up when objects are garbage collected.
        However, for long-running processes, explicit cleanup is recommended.

        This method explicitly closes critical resources (connection pools, database
        connections) and then clears the reference to allow GC to handle the rest.

        Note: Designed to be called from the background event loop via
        `asyncio.run_coroutine_threadsafe()`.

        """
        if self.memory is None:
            return

        logger.debug("Closing AsyncMemory resources")
        try:
            loop = asyncio.get_running_loop()

            # Explicitly close critical resources (connection pools, DB connections)
            # Other resources will be cleaned up by __del__ methods during GC

            # PGVector connection pool
            vs = getattr(self.memory, "vector_store", None)
            if vs and hasattr(vs, "connection_pool") and vs.connection_pool:
                try:
                    pool = vs.connection_pool
                    if hasattr(pool, "close"):
                        await loop.run_in_executor(None, pool.close)
                    elif hasattr(pool, "closeall"):
                        await loop.run_in_executor(None, pool.closeall)
                except Exception:
                    logger.exception("Error closing vector store connection pool")

            # Graph store (Neo4jGraph)
            graph = getattr(self.memory, "graph", None)
            if graph:
                try:
                    if hasattr(graph, "close") and not asyncio.iscoroutinefunction(graph.close):
                        await loop.run_in_executor(None, graph.close)
                    elif hasattr(graph, "aclose"):
                        await graph.aclose()
                    elif hasattr(graph, "driver") and hasattr(graph.driver, "close"):
                        await loop.run_in_executor(None, graph.driver.close)
                except Exception:
                    logger.exception("Error closing graph store")

            # SQLite connection
            db = getattr(self.memory, "db", None)
            if db and hasattr(db, "close"):
                try:
                    await loop.run_in_executor(None, db.close)
                except Exception:
                    logger.exception("Error closing database connection")

        except Exception:
            logger.exception("Error during AsyncMemory resource cleanup")
        finally:
            # Clear reference - remaining resources will be cleaned up by __del__ methods
            self.memory = None
            logger.debug("AsyncMemory resources closed")

    # Background event loop (class-level, process-wide)
    _bg_loop: asyncio.AbstractEventLoop | None = None
    _bg_thread: threading.Thread | None = None
    _bg_ready = threading.Event()
    _bg_lock = threading.Lock()

    @classmethod
    def ensure_bg_loop(cls) -> asyncio.AbstractEventLoop:
        """Ensure that a background asyncio event loop is running in a dedicated thread.

        This method provides a long-lived, reusable, process-wide background event loop
        for submitting and running coroutines from synchronous code or from threads that
        do not have a running event loop. The loop is created once and reused for the
        entire plugin lifecycle, ensuring efficient resource usage and avoiding the
        overhead of creating new loops for each operation.

        The event loop runs in a dedicated daemon thread and persists until the plugin
        is shut down via shutdown(). This design ensures:
        - Long lifecycle: Loop exists for the entire plugin runtime
        - Reusability: Same loop instance is returned for all operations
        - Thread safety: Access is guarded by a class-level lock
        - Resource efficiency: No per-operation loop creation overhead

        Returns:
            asyncio.AbstractEventLoop: The long-lived, reusable background event loop object.

        Raises:
            RuntimeError: If the background event loop fails to start.

        """
        with cls._bg_lock:
            # Reuse the existing long-lived loop if already running
            if cls._bg_loop and cls._bg_thread and cls._bg_thread.is_alive():
                logger.debug("Reusing existing long-lived background event loop")
                return cls._bg_loop

            logger.info("Starting new long-lived background event loop")
            # Define the function that runs in the new background thread
            def _runner() -> None:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                cls._bg_loop = loop
                cls._bg_ready.set()
                logger.info("Background event loop started (long-lived)")
                loop.run_forever()  # Run the event loop forever (long lifecycle)

            # Prepare to start a new background thread
            cls._bg_ready.clear()
            t = threading.Thread(target=_runner, name="mem0-bg-loop", daemon=True)
            t.start()
            cls._bg_thread = t
            cls._bg_ready.wait()  # Wait until the loop is ready

            loop = cls._bg_loop
            if loop is None:
                msg = "Background event loop failed to start"
                logger.error(msg)
                raise RuntimeError(msg)
            logger.info("Background event loop ready (long-lived, reusable)")
            return loop

    @classmethod
    def shutdown(cls, timeout: float = 3.0) -> None:
        """Best-effort graceful shutdown of the background event loop.

        - Attempts to wait up to `timeout` seconds for pending tasks to finish.
        - Stops the loop and joins the background thread (best-effort).
        - Safe to call multiple times.
        """
        loop = cls._bg_loop
        thread = cls._bg_thread
        if loop is None:
            logger.debug("No background event loop to shutdown")
            return

        logger.info("Shutting down background event loop (timeout: %s)", timeout)

        async def _drain_tasks(t: float) -> None:
            # Exclude the current task and wait for others (best-effort)
            with contextlib.suppress(Exception):
                pending = [tsk for tsk in asyncio.all_tasks() if tsk is not asyncio.current_task()]
                if pending:
                    logger.info("Waiting for %d pending tasks to complete", len(pending))
                    await asyncio.wait(pending, timeout=t)

        fut = asyncio.run_coroutine_threadsafe(_drain_tasks(timeout), loop)
        with contextlib.suppress(Exception):
            fut.result(timeout=timeout + 1.0)
        with contextlib.suppress(Exception):
            loop.call_soon_threadsafe(loop.stop)
        if thread and thread.is_alive():
            with contextlib.suppress(Exception):
                thread.join(timeout=timeout)
        # Clear references
        cls._bg_loop = None
        cls._bg_thread = None
        logger.info("Background event loop shutdown completed")

    async def search(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Search for memories based on a query.

        Args:
            payload (dict): Search parameters. Supported keys:
                - query (str): Query to search for.
                - user_id (str, optional): ID of the user.
                - agent_id (str, optional): ID of the agent.
                - run_id (str, optional): ID of the run.
                - limit (int, optional): Max number of results.
                - filters (dict, optional): Metadata filters, supporting:
                    * {"key": "value"} (exact match)
                    * {"key": {"eq"/"ne"/"in"/"nin"/"gt"/"gte"/"lt"/"lte"/"contains"/"icontains"}: ...}
                    * {"key": "*"} (wildcard)
                    * {"AND"/"OR"/"NOT": [filters,...]} (logic ops)
                - threshold (float, optional): Minimum score (not used in local mode).

        Returns:
            list[dict]: List of memory search results.

        """  # noqa: E501
        await self.create()
        query = payload.get("query", "")
        filters = payload.get("filters")
        limit = payload.get("limit")

        # Normalize limit to int when possible
        lim: int | None
        try:
            lim = int(limit) if limit is not None else None
        except (TypeError, ValueError):
            lim = None

        # Build kwargs with non-empty args to simplify branching
        kwargs: dict[str, Any] = {}
        if lim is not None:
            kwargs["limit"] = lim
        if isinstance(filters, dict):
            kwargs["filters"] = filters
        else:
            if payload.get("user_id"):
                kwargs["user_id"] = payload.get("user_id")
            if payload.get("agent_id"):
                kwargs["agent_id"] = payload.get("agent_id")
            if payload.get("run_id"):
                kwargs["run_id"] = payload.get("run_id")

        try:
            async with self._semaphore:
                results = await self.memory.search(query, **kwargs)
            normalized = _normalize_search_results(results)
        except Exception:
            logger.exception("Error during async memory search")
            raise
        else:
            return normalized

    async def add(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a new memory.

        Adds new memories scoped to a single session id (e.g. user_id, agent_id, or run_id).
        One of those ids is required.

        Args:
            payload (dict): A dictionary containing all parameters for adding a memory, including:
                - messages (str or list[dict[str, str]]): The message content or list of messages
                  (e.g., [{"role": "user", "content": "Hello"}, ...]) to process and store.
                - user_id (str, optional): ID of the user creating the memory.
                - agent_id (str, optional): ID of the agent creating the memory.
                - run_id (str, optional): ID of the run creating the memory.
                - metadata (dict or str, optional): Metadata to store with the memory.
                  Can be a dict or a JSON string.
                - infer (bool, optional): If True (default), uses LLM to extract key facts
                  and manage memories.
                - memory_type (str, optional): Type of memory. Defaults to conversational or factual.
                  Use "procedural_memory" for procedural type.
                - prompt (str, optional): Custom prompt to use for memory creation.
                - expiration_date (str, optional): Expiration date/TTL (e.g., YYYY-MM-DD or ISO string),
                  only when supported by the installed local Mem0 SDK.

        Returns:
            dict: Result of the memory addition, typically with items added/updated (in "results"),
            and possibly "relations" if graph store is enabled.

        """  # noqa: E501
        await self.create()
        metadata = _normalize_add_metadata(payload.get("metadata"), user_id=payload.get("user_id"))
        messages = _normalize_add_messages(payload.get("messages"), user_id=payload.get("user_id"))

        kwargs: dict[str, Any] = {}
        if payload.get("user_id"):
            kwargs["user_id"] = payload.get("user_id")
        if payload.get("agent_id"):
            kwargs["agent_id"] = payload.get("agent_id")
        if payload.get("run_id"):
            kwargs["run_id"] = payload.get("run_id")
        if metadata is not None:
            kwargs["metadata"] = metadata
        expiration_date = payload.get("expiration_date")
        if expiration_date and _ASYNC_ADD_SUPPORTS_EXPIRATION:
            kwargs["expiration_date"] = expiration_date
        elif expiration_date:
            logger.warning(
                "Ignoring expiration_date for async Mem0 client because installed AsyncMemory.add does not support it (user_id: %s, requested_expiration_date: %s)",
                payload.get("user_id") or "-",
                expiration_date,
            )
        if self.use_custom_prompt:
            kwargs["prompt"] = self.custom_prompt

        # Skip add when messages is empty/blank, return response aligned with mem0 add result shape
        if messages is None or (
            isinstance(messages, str) and messages.strip() == ""
        ) or (
            isinstance(messages, (list, tuple)) and len(messages) == 0
        ):
            return ADD_SKIP_RESULT

        try:
            # Limit concurrent add() to avoid exhausting DB connection pool
            async with self._semaphore:
                # Await to ensure persistence before returning
                result = await self.memory.add(messages, **kwargs)
        except Exception as error:
            traceback_text = "".join(
                traceback.format_exception(type(error), error, error.__traceback__),
            ).strip()
            logger.error(
                "Memory addition failed in async Mem0 client (user_id: %s, agent_id: %s, run_id: %s, message_count: %d, message_shapes: %s, metadata_present: %s, expiration_date: %s): %s",
                payload.get("user_id") or "-",
                payload.get("agent_id") or "-",
                payload.get("run_id") or "-",
                _count_payload_messages(messages),
                _message_shapes(messages),
                metadata is not None,
                expiration_date or "-",
                format_exception(error),
            )
            if traceback_text:
                logger.error("Async Mem0 add traceback (user_id: %s):\n%s", payload.get("user_id") or "-", traceback_text)
            logger.debug(
                "Stack trace for async Mem0 memory addition failure",
                exc_info=(type(error), error, error.__traceback__),
            )
            raise
        else:
            return result

    async def get_all(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Get all memories based on user/agent/run identifiers with optional filters.

        Args:
            params (dict): Parameters including:
                - user_id (str, optional): User ID to filter by.
                - agent_id (str, optional): Agent ID to filter by.
                - run_id (str, optional): Run ID to filter by.
                - limit (int, optional): Maximum number of results to return.
                - filters (dict, optional): Advanced metadata filters.

        Returns:
            list[dict]: List of memory objects.

        """
        await self.create()

        # Build kwargs with all provided parameters
        kwargs: dict[str, Any] = {}

        # Add entity IDs if provided
        if params.get("user_id"):
            kwargs["user_id"] = params.get("user_id")
        if params.get("agent_id"):
            kwargs["agent_id"] = params.get("agent_id")
        if params.get("run_id"):
            kwargs["run_id"] = params.get("run_id")

        # Add optional parameters
        limit = params.get("limit")
        if limit is not None:
            with contextlib.suppress(TypeError, ValueError):
                kwargs["limit"] = int(limit)

        filters = params.get("filters")
        if isinstance(filters, dict):
            kwargs["filters"] = filters

        # Mem0's get_all always returns {"results": [...]} format
        try:
            async with self._semaphore:
                result = await self.memory.get_all(**kwargs)
            memories = result.get("results", []) if isinstance(result, dict) else []
        except Exception:
            logger.exception("Error during async get_all operation")
            raise
        else:
            return memories

    async def get(self, memory_id: str) -> dict[str, Any]:
        """Get a single memory by ID.

        Args:
            memory_id (str): The ID of the memory to retrieve.

        Returns:
            dict: Memory object with id, memory, metadata, created_at, updated_at, etc.

        """
        await self.create()
        try:
            async with self._semaphore:
                result = await self.memory.get(memory_id)
        except Exception:
            logger.exception("Error retrieving memory %s (async)", memory_id)
            raise
        else:
            return result

    async def update(self, memory_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update a memory by ID.

        Args:
            memory_id (str): ID of the memory to update.
            payload (dict): Dictionary containing new content under the "text" key.

        Returns:
            dict: Success message indicating the memory was updated.

        """
        await self.create()
        try:
            async with self._semaphore:
                result = await self.memory.update(memory_id, payload.get("text"))
        except Exception:
            logger.exception("Error updating memory %s (async)", memory_id)
            raise
        else:
            return result

    async def delete(self, memory_id: str) -> dict[str, Any]:
        """Delete a memory by ID.

        Args:
            memory_id (str): The ID of the memory to delete.

        Returns:
            dict: Success message, typically {"message": "Memory deleted successfully!"}.

        """
        await self.create()
        try:
            async with self._semaphore:
                result = await self.memory.delete(memory_id)
        except Exception:
            logger.exception("Error deleting memory %s (async)", memory_id)
            raise
        else:
            return result

    async def delete_all(self, params: dict[str, Any]) -> dict[str, Any]:
        """Delete all memories matching the given filters.

        Args:
            params (dict): Parameters including:
                - user_id (str, optional): User ID to filter by.
                - agent_id (str, optional): Agent ID to filter by.
                - run_id (str, optional): Run ID to filter by.

        Returns:
            dict: Result of the deletion operation.

        """
        await self.create()
        try:
            async with self._semaphore:
                result = await self.memory.delete_all(
                    user_id=params.get("user_id"),
                    agent_id=params.get("agent_id"),
                    run_id=params.get("run_id"),
                )
        except Exception:
            logger.exception("Error during async delete_all operation")
            raise
        else:
            return result

    async def history(self, memory_id: str) -> list[dict[str, Any]]:
        """Get the history of changes for a specific memory.

        Args:
            memory_id (str): The ID of the memory to get history for.

        Returns:
            list[dict]: List of history records with old_memory, new_memory, event, created_at, etc.

        """
        await self.create()
        try:
            async with self._semaphore:
                result = await self.memory.history(memory_id)
        except Exception:
            logger.exception("Error retrieving history for memory %s (async)", memory_id)
            raise
        else:
            return result


def _cleanup_async_client(client: AsyncLocalClient, context: str = "cleanup") -> None:
    """Cleanup AsyncLocalClient resources via background event loop.

    This helper function provides a unified way to cleanup AsyncLocalClient
    instances, avoiding code duplication.

    Args:
        client: The AsyncLocalClient instance to cleanup.
        context: Context string for logging (e.g., "replacement", "reset").

    """
    if client is None:
        return

    loop = AsyncLocalClient._bg_loop  # noqa: SLF001
    if loop is not None and loop.is_running():
        try:
            fut = asyncio.run_coroutine_threadsafe(client.aclose(), loop)
            # Waiting for cleanup to complete
            fut.result(timeout=2.0)
        except Exception:
            logger.exception("Failed to cleanup async client resources during %s", context)
    else:
        logger.debug("No background loop available for async cleanup during %s", context)


def get_local_client(credentials: dict[str, Any]) -> LocalClient:
    """Get or create LocalClient instance, recreating if config changed.

    This function provides a module-level factory for LocalClient instances,
    ensuring resource reuse while supporting configuration changes.

    All reads and writes to module-level variables are protected by
    threading.Lock to ensure thread safety in multi-threaded environments.

    Args:
        credentials: Configuration dictionary for the LocalClient.

    Returns:
        LocalClient: The LocalClient instance, reused if config unchanged.

    """
    global _local_client, _local_client_config_hash  # noqa: PLW0603

    config_hash = _get_config_hash(credentials)

    # All reads and writes are protected by lock to ensure thread safety
    with _local_client_lock:
        # If config changed or client doesn't exist, create new instance
        if _local_client is None or _local_client_config_hash != config_hash:
            # LocalClient resources (PGVector, SQLiteManager) have __del__ methods
            # that will be called during GC when the old reference is overwritten.
            # LocalClient doesn't have a close() method, so we rely on __del__
            # methods in mem0 resources for cleanup.
            if _local_client is not None:
                logger.debug("Replacing LocalClient due to config change")
            _local_client = LocalClient(credentials)
            _local_client_config_hash = config_hash
        return _local_client


def get_async_local_client(credentials: dict[str, Any]) -> AsyncLocalClient:
    """Get or create AsyncLocalClient instance, recreating if config changed.

    This function provides a module-level factory for AsyncLocalClient instances,
    ensuring resource reuse while supporting configuration changes.

    All reads and writes to module-level variables are protected by
    threading.Lock to ensure thread safety in multi-threaded environments.

    Args:
        credentials: Configuration dictionary for the AsyncLocalClient.

    Returns:
        AsyncLocalClient: The AsyncLocalClient instance, reused if config unchanged.

    """
    global _async_client, _async_client_config_hash  # noqa: PLW0603

    config_hash = _get_config_hash(credentials)

    # All reads and writes are protected by lock to ensure thread safety
    with _async_client_lock:
        # If config changed or client doesn't exist, create new instance
        if _async_client is None or _async_client_config_hash != config_hash:
            # Cleanup old client before creating new one to prevent resource leaks
            old_client = _async_client
            if old_client is not None:
                logger.debug(
                    "Replacing AsyncLocalClient due to config change, cleaning up old instance",
                )
                _cleanup_async_client(old_client, context="replacement")
            _async_client = AsyncLocalClient(credentials)
            _async_client_config_hash = config_hash
        return _async_client


def reset_clients() -> None:
    """Reset client instances (useful for testing).

    This function clears the cached client instances, forcing new instances
    to be created on the next call to get_local_client() or get_async_local_client().

    For AsyncLocalClient, this also attempts to cleanup resources (HTTP sessions,
    database connections, etc.) to prevent resource leaks.

    """
    global _local_client, _local_client_config_hash  # noqa: PLW0603
    global _async_client, _async_client_config_hash  # noqa: PLW0603

    with _local_client_lock:
        _local_client = None
        _local_client_config_hash = None

    with _async_client_lock:
        # Cleanup async client resources before resetting
        old_client = _async_client
        if old_client is not None:
            _cleanup_async_client(old_client, context="reset")

        _async_client = None
        _async_client_config_hash = None
