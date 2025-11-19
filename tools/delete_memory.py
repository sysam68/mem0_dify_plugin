import asyncio
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from utils.config_builder import is_async_mode
from utils.constants import DELETE_ACCEPT_RESULT
from utils.mem0_client import AsyncLocalClient, LocalClient


class DeleteMemoryTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        memory_id = tool_parameters["memory_id"]

        try:
            async_mode = is_async_mode(self.runtime.credentials)

            # In sync mode, check if memory exists before deleting
            if not async_mode:
                client = LocalClient(self.runtime.credentials)
                # Check if memory exists
                existing = client.get(memory_id)
                if not existing or not isinstance(existing, dict):
                    error_message = f"Memory not found: {memory_id}"
                    yield self.create_json_message(
                        {"status": "ERROR", "messages": error_message, "results": {}})
                    yield self.create_text_message(f"Error: {error_message}")
                    return

                # Wrap delete call in try-except to catch Mem0 internal errors
                try:
                    result = client.delete(memory_id)
                except AttributeError:
                    # Mem0 internal error: memory was deleted between get() and delete()
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

                yield self.create_json_message({
                    "status": "SUCCESS",
                    "messages": {"memory_id": memory_id},
                    **DELETE_ACCEPT_RESULT,
                })
                yield self.create_text_message("Asynchronous memory deletion has been accepted.")

        except (ValueError, RuntimeError, TypeError, AttributeError) as e:
            error_message = f"Error: {e!s}"
            yield self.create_json_message(
                {"status": "ERROR", "messages": error_message, "results": []})
            yield self.create_text_message(f"Failed to delete memory: {error_message}")
