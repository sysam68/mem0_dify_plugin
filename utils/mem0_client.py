"""Client adapter for Mem0 local mode only."""

from __future__ import annotations

import asyncio
import contextlib
import json
import threading
from typing import Any

from mem0 import AsyncMemory, Memory

from .config_builder import build_local_mem0_config
from .constants import ADD_SKIP_RESULT, CUSTOM_PROMPT, MAX_CONCURRENT_MEMORY_OPERATIONS
from .logger import get_logger

logger = get_logger(__name__)


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
                "metadata": r.get("metadata") or {},
                "created_at": r.get("created_at") or r.get("timestamp") or "",
            },
        )
    return normalized


class LocalClient:
    """Local Mem0 client using configured providers."""

    def __init__(self, credentials: dict[str, Any]) -> None:
        """Initialize the LocalClient.

        Args:
            credentials (dict): Configuration for the LocalClient.

        """
        logger.info("Initializing LocalClient")
        config = build_local_mem0_config(credentials)
        self.memory = Memory.from_config(config)
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

        """
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

        logger.info(
            "Searching memories with query: %s..., filters: %s, limit: %s",
            query[:50],
            bool(kwargs.get("filters")),
            kwargs.get("limit"),
        )
        try:
            results = self.memory.search(query, **kwargs)
            normalized = _normalize_search_results(results)
        except Exception:
            logger.exception("Error during memory search")
            raise
        else:
            logger.info("Search completed, found %d results", len(normalized))
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

        Returns:
            dict: Result of the memory addition, typically with items added/updated (in "results"),
            and possibly "relations" if graph store is enabled.

        """
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
        if self.use_custom_prompt:
            kwargs["prompt"] = self.custom_prompt

        # Use messages directly if provided; assume upstream has validated inputs
        messages = payload.get("messages")
        user_id = kwargs.get("user_id") or payload.get("user_id")
        msg_count = len(messages) if isinstance(messages, list) else 1
        logger.info("Adding memory for user_id: %s, messages count: %d", user_id, msg_count)
        try:
            result = self.memory.add(messages, **kwargs)
        except Exception:
            logger.exception("Error during memory addition")
            raise
        else:
            logger.info("Memory added successfully")
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
        logger.info("Getting all memories with filters: %s", kwargs)
        try:
            result = self.memory.get_all(**kwargs)
            memories = result.get("results", []) if isinstance(result, dict) else []
        except Exception:
            logger.exception("Error during get_all operation")
            raise
        else:
            logger.info("Retrieved %d memories", len(memories))
            return memories

    def get(self, memory_id: str) -> dict[str, Any]:
        """Get a single memory by ID.

        Args:
            memory_id (str): The ID of the memory to retrieve.

        Returns:
            dict: Memory object with id, memory, metadata, created_at, updated_at, etc.

        """
        logger.info("Getting memory by ID: %s", memory_id)
        try:
            result = self.memory.get(memory_id)
        except Exception:
            logger.exception("Error retrieving memory %s", memory_id)
            raise
        else:
            if result:
                logger.info("Memory %s retrieved successfully", memory_id)
            else:
                logger.warning("Memory %s not found", memory_id)
            return result

    def update(self, memory_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update a memory by ID.

        Args:
            memory_id (str): ID of the memory to update.
            payload (dict): Dictionary containing new content under the "text" key.

        Returns:
            dict: Success message indicating the memory was updated.

        """
        logger.info("Updating memory %s", memory_id)
        try:
            result = self.memory.update(memory_id, payload.get("text"))
        except Exception:
            logger.exception("Error updating memory %s", memory_id)
            raise
        else:
            logger.info("Memory %s updated successfully", memory_id)
            return result

    def delete(self, memory_id: str) -> dict[str, Any]:
        """Delete a memory by ID.

        Args:
            memory_id (str): The ID of the memory to delete.

        Returns:
            dict: Success message, typically {"message": "Memory deleted successfully!"}.

        """
        logger.info("Deleting memory %s", memory_id)
        try:
            result = self.memory.delete(memory_id)
        except Exception:
            logger.exception("Error deleting memory %s", memory_id)
            raise
        else:
            logger.info("Memory %s deleted successfully", memory_id)
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
        logger.warning("Deleting all memories with filters: %s", params)
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
            logger.info("Delete all operation completed: %s", result)
            return result

    def history(self, memory_id: str) -> list[dict[str, Any]]:
        """Get the history of changes for a specific memory.

        Args:
            memory_id (str): The ID of the memory to get history for.

        Returns:
            list[dict]: List of history records with old_memory, new_memory, event, created_at, etc.

        """
        logger.info("Getting history for memory %s", memory_id)
        try:
            result = self.memory.history(memory_id)
        except Exception:
            logger.exception("Error retrieving history for memory %s", memory_id)
            raise
        else:
            logger.info("Retrieved %d history records for memory %s", len(result), memory_id)
            return result


class AsyncLocalClient:
    """Async local Mem0 client using configured providers."""

    _instance: AsyncLocalClient | None = None
    _instance_lock = threading.Lock()

    def __new__(cls, _credentials: dict[str, Any]) -> AsyncLocalClient:
        """Create or return the singleton instance of AsyncLocalClient.

        Ensures a single process-wide instance guarded by a class-level lock,
        ignoring repeated constructor calls.
        """
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, credentials: dict[str, Any]) -> None:
        # Guard against re-initializing singleton
        if getattr(self, "_initialized", False):
            logger.debug("AsyncLocalClient already initialized, skipping re-initialization")
            return
        logger.info("Initializing AsyncLocalClient")
        self.config = build_local_mem0_config(credentials)
        self.memory = None
        # Async lock to protect one-time asynchronous initialization.
        self._create_lock = asyncio.Lock()
        # Semaphore to limit the concurrency of memory operations
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_MEMORY_OPERATIONS)
        # Toggle whether to use custom prompt
        self.use_custom_prompt = True
        self.custom_prompt = CUSTOM_PROMPT
        self._initialized = True
        logger.info("AsyncLocalClient initialized successfully")

    async def create(self) -> AsyncMemory:
        """Lazily create AsyncMemory once."""
        if self.memory is not None:
            return self.memory
        async with self._create_lock:
            if self.memory is None:
                logger.info("Creating AsyncMemory instance")
                self.memory = await AsyncMemory.from_config(self.config)
                logger.info("AsyncMemory instance created successfully")
        return self.memory

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

        """
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

        logger.info(
            "Searching memories (async) with query: %s..., filters: %s, limit: %s",
            query[:50],
            bool(kwargs.get("filters")),
            kwargs.get("limit"),
        )
        try:
            async with self._semaphore:
                results = await self.memory.search(query, **kwargs)
            normalized = _normalize_search_results(results)
        except Exception:
            logger.exception("Error during async memory search")
            raise
        else:
            logger.info("Search completed (async), found %d results", len(normalized))
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

        Returns:
            dict: Result of the memory addition, typically with items added/updated (in "results"),
            and possibly "relations" if graph store is enabled.

        """
        await self.create()
        metadata = payload.get("metadata")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = None

        kwargs: dict[str, Any] = {}
        if payload.get("user_id"):
            kwargs["user_id"] = payload.get("user_id")
        if payload.get("agent_id"):
            kwargs["agent_id"] = payload.get("agent_id")
        if payload.get("run_id"):
            kwargs["run_id"] = payload.get("run_id")
        if metadata is not None:
            kwargs["metadata"] = metadata
        if self.use_custom_prompt:
            kwargs["prompt"] = self.custom_prompt

        messages = payload.get("messages")
        # Skip add when messages is empty/blank, return response aligned with mem0 add result shape
        if messages is None or (
            isinstance(messages, str) and messages.strip() == ""
        ) or (
            isinstance(messages, (list, tuple)) and len(messages) == 0
        ):
            return ADD_SKIP_RESULT

        user_id = kwargs.get("user_id") or payload.get("user_id")
        msg_count = len(messages) if isinstance(messages, list) else 1
        logger.info("Adding memory (async) for user_id: %s, messages count: %d", user_id, msg_count)
        try:
            # Limit concurrent add() to avoid exhausting DB connection pool
            async with self._semaphore:
                # Await to ensure persistence before returning
                result = await self.memory.add(messages, **kwargs)
        except Exception:
            logger.exception("Error during async memory addition")
            raise
        else:
            logger.info("Memory added successfully (async)")
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
        logger.info("Getting all memories (async) with filters: %s", kwargs)
        try:
            async with self._semaphore:
                result = await self.memory.get_all(**kwargs)
            memories = result.get("results", []) if isinstance(result, dict) else []
        except Exception:
            logger.exception("Error during async get_all operation")
            raise
        else:
            logger.info("Retrieved %d memories (async)", len(memories))
            return memories

    async def get(self, memory_id: str) -> dict[str, Any]:
        """Get a single memory by ID.

        Args:
            memory_id (str): The ID of the memory to retrieve.

        Returns:
            dict: Memory object with id, memory, metadata, created_at, updated_at, etc.

        """
        logger.info("Getting memory (async) by ID: %s", memory_id)
        await self.create()
        try:
            async with self._semaphore:
                result = await self.memory.get(memory_id)
        except Exception:
            logger.exception("Error retrieving memory %s (async)", memory_id)
            raise
        else:
            if result:
                logger.info("Memory %s retrieved successfully (async)", memory_id)
            else:
                logger.warning("Memory %s not found (async)", memory_id)
            return result

    async def update(self, memory_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update a memory by ID.

        Args:
            memory_id (str): ID of the memory to update.
            payload (dict): Dictionary containing new content under the "text" key.

        Returns:
            dict: Success message indicating the memory was updated.

        """
        logger.info("Updating memory (async) %s", memory_id)
        await self.create()
        try:
            async with self._semaphore:
                result = await self.memory.update(memory_id, payload.get("text"))
        except Exception:
            logger.exception("Error updating memory %s (async)", memory_id)
            raise
        else:
            logger.info("Memory %s updated successfully (async)", memory_id)
            return result

    async def delete(self, memory_id: str) -> dict[str, Any]:
        """Delete a memory by ID.

        Args:
            memory_id (str): The ID of the memory to delete.

        Returns:
            dict: Success message, typically {"message": "Memory deleted successfully!"}.

        """
        logger.info("Deleting memory (async) %s", memory_id)
        await self.create()
        try:
            async with self._semaphore:
                result = await self.memory.delete(memory_id)
        except Exception:
            logger.exception("Error deleting memory %s (async)", memory_id)
            raise
        else:
            logger.info("Memory %s deleted successfully (async)", memory_id)
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
        logger.warning("Deleting all memories (async) with filters: %s", params)
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
            logger.info("Delete all operation completed (async): %s", result)
            return result

    async def history(self, memory_id: str) -> list[dict[str, Any]]:
        """Get the history of changes for a specific memory.

        Args:
            memory_id (str): The ID of the memory to get history for.

        Returns:
            list[dict]: List of history records with old_memory, new_memory, event, created_at, etc.

        """
        logger.info("Getting history (async) for memory %s", memory_id)
        await self.create()
        try:
            async with self._semaphore:
                result = await self.memory.history(memory_id)
        except Exception:
            logger.exception("Error retrieving history for memory %s (async)", memory_id)
            raise
        else:
            logger.info("Retrieved %d history records for memory %s (async)", len(result), memory_id)
            return result
