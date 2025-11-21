"""Dify tool for deleting a memory from Mem0 by ID."""

import asyncio
import logging
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from utils.config_builder import is_async_mode
from utils.constants import DELETE_ACCEPT_RESULT
from utils.mem0_client import AsyncLocalClient, LocalClient

logger = logging.getLogger(__name__)


class DeleteMemoryTool(Tool):
    """Tool that deletes a specific memory by its ID."""

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        memory_id = tool_parameters["memory_id"]

        try:
            async_mode = is_async_mode(self.runtime.credentials)
            logger.info("Deleting memory %s, async_mode: %s", memory_id, async_mode)

            # In sync mode, check if memory exists before deleting
            if not async_mode:
                client = LocalClient(self.runtime.credentials)
                # Check if memory exists
                existing = client.get(memory_id)
                if not existing or not isinstance(existing, dict):
                    logger.warning("Memory not found: %s", memory_id)
                    error_message = f"Memory not found: {memory_id}"
                    yield self.create_json_message(
                        {"status": "ERROR", "messages": error_message, "results": {}})
                    yield self.create_text_message(f"Error: {error_message}")
                    return

                # Wrap delete call in try-except to catch Mem0 internal errors
                try:
                    result = client.delete(memory_id)
                    logger.info("Memory %s deleted successfully", memory_id)
                except AttributeError:
                    # Mem0 internal error: memory was deleted between get() and delete()
                    logger.warning("Memory %s not found or already deleted", memory_id)
                    error_message = f"Memory not found or already deleted: {memory_id}"
                    yield self.create_json_message(
                        {"status": "ERROR", "messages": error_message, "results": {}})
                    yield self.create_text_message(f"Error: {error_message}")
                    return

                yield self.create_json_message({
                    "status": "SUCCESS",
                    "messages": {"memory_id": memory_id},
                    "results": result,
                })
                yield self.create_text_message(f"Memory {memory_id} deleted successfully!")
            else:
                client = AsyncLocalClient(self.runtime.credentials)
                # Submit delete to background event loop without awaiting (non-blocking)
                loop = AsyncLocalClient.ensure_bg_loop()
                asyncio.run_coroutine_threadsafe(client.delete(memory_id), loop)
                logger.info("Memory deletion submitted to background loop: %s", memory_id)

                yield self.create_json_message({
                    "status": "SUCCESS",
                    "messages": {"memory_id": memory_id},
                    **DELETE_ACCEPT_RESULT,
                })
                yield self.create_text_message("Asynchronous memory deletion has been accepted.")

        except Exception as e:
            # Catch all exceptions to ensure workflow continues
            logger.exception("Error deleting memory %s", memory_id)
            error_message = f"Error: {e!s}"
            yield self.create_json_message(
                {"status": "ERROR", "messages": error_message, "results": []})
            yield self.create_text_message(f"Failed to delete memory: {error_message}")
