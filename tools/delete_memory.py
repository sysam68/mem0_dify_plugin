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
            if async_mode:
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
            else:
                client = LocalClient(self.runtime.credentials)
                result = client.delete(memory_id)
                yield self.create_json_message({
                    "status": "SUCCESS",
                    "messages": {"memory_id": memory_id},
                    "results": result,
                })
                yield self.create_text_message(f"Memory {memory_id} deleted successfully!")

        except (ValueError, RuntimeError, TypeError) as e:
            error_message = f"Error: {e!s}"
            yield self.create_json_message(
                {"status": "ERROR", "messages": error_message, "results": []})
            yield self.create_text_message(f"Failed to delete memory: {error_message}")
