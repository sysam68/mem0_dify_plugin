"""Dify tool for retrieving memory history from Mem0."""

import asyncio
import logging
from collections.abc import Generator
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from utils.config_builder import is_async_mode
from utils.constants import HISTORY_OPERATION_TIMEOUT
from utils.mem0_client import AsyncLocalClient, LocalClient

logger = logging.getLogger(__name__)


class GetMemoryHistoryTool(Tool):
    """Tool that retrieves the change history of a specific memory by ID."""

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        memory_id = tool_parameters["memory_id"]

        try:
            async_mode = is_async_mode(self.runtime.credentials)
            # Get timeout from parameters, use default if not provided
            timeout = tool_parameters.get("timeout")
            if timeout is None:
                timeout = HISTORY_OPERATION_TIMEOUT
            else:
                try:
                    timeout = float(timeout)
                except (TypeError, ValueError):
                    logger.warning(
                        "Invalid timeout value: %s, using default: %d",
                        timeout,
                        HISTORY_OPERATION_TIMEOUT,
                    )
                    timeout = HISTORY_OPERATION_TIMEOUT
            logger.info(
                "Getting memory history for %s, async_mode: %s, timeout: %s",
                memory_id,
                async_mode,
                timeout,
            )
            # Initialize results with default value to ensure it's always defined
            results: list[dict[str, Any]] = []
            if async_mode:
                # Note: AsyncLocalClient is a singleton, so no explicit resource cleanup needed.
                # Resources are managed at plugin lifecycle level via AsyncLocalClient.shutdown()
                client = AsyncLocalClient(self.runtime.credentials)
                # ensure_bg_loop() returns a long-lived, reusable event loop
                loop = AsyncLocalClient.ensure_bg_loop()
                future = asyncio.run_coroutine_threadsafe(client.history(memory_id), loop)
                try:
                    results = future.result(timeout=timeout)
                except FuturesTimeoutError:
                    # Cancel the future to prevent the background task from hanging
                    future.cancel()
                    logger.exception(
                        "History operation timed out after %s seconds for memory_id: %s",
                        timeout,
                        memory_id,
                    )
                    # Service degradation: return empty results to allow workflow to continue
                    results = []
                except Exception as e:
                    # Catch all other exceptions (network errors, connection errors, DNS failures,
                    # SSL errors, authentication failures, etc.) to ensure service degradation
                    # works for all failure scenarios, not just timeouts
                    logger.exception(
                        "History operation failed with error: %s (memory_id: %s)",
                        type(e).__name__,
                        memory_id,
                    )
                    # Service degradation: return empty results to allow workflow to continue
                    results = []
            else:
                # Sync mode: no timeout protection (blocking call)
                # If timeout protection is needed, use async_mode=true
                client = LocalClient(self.runtime.credentials)
                try:
                    results = client.history(memory_id)
                except Exception as e:
                    # Catch all exceptions for sync mode to ensure service degradation
                    logger.exception(
                        "History operation failed with error: %s (memory_id: %s)",
                        type(e).__name__,
                        memory_id,
                    )
                    # Service degradation: return empty results to allow workflow to continue
                    results = []
            logger.info("Retrieved %d history records for memory %s", len(results), memory_id)

            # JSON output
            history = []
            for h in results or []:
                if not isinstance(h, dict):
                    continue
                history.append({
                    "memory_id": h.get("memory_id"),
                    "old_memory": h.get("old_memory"),
                    "new_memory": h.get("new_memory"),
                    "event": h.get("event"),
                    "created_at": h.get("created_at"),
                    "updated_at": h.get("updated_at"),
                    "is_deleted": h.get("is_deleted", False),
                })

            yield self.create_json_message({
                "status": "SUCCESS",
                "messages": {"memory_id": memory_id},
                "results": history,
            })

            # Text output
            text_response = f"Found {len(history)} history records for memory {memory_id}\n\n"
            if history:
                for idx, h in enumerate(history, 1):
                    text_response += (
                        f"{idx}. Memory ID: {h.get('memory_id', '')}\n"
                        f"   Old Memory: {h.get('old_memory', '')}\n"
                        f"   New Memory: {h.get('new_memory', '')}\n"
                        f"   Event: {h.get('event', '')}\n"
                        f"   Created: {h.get('created_at', '')}\n"
                        f"   Updated: {h.get('updated_at', '')}\n"
                        f"   Is Deleted: {h.get('is_deleted', False)}\n\n"
                    )
            yield self.create_text_message(text_response)

        except Exception as e:
            # Catch all exceptions to ensure workflow continues
            logger.exception("Error getting memory history for %s", memory_id)
            error_message = f"Error: {e!s}"
            yield self.create_json_message(
                {"status": "ERROR", "messages": error_message, "results": []})
            yield self.create_text_message(f"Failed to get memory history: {error_message}")
