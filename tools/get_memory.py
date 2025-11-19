import asyncio
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from utils.config_builder import is_async_mode
from utils.mem0_client import AsyncLocalClient, LocalClient


class GetMemoryTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        memory_id = tool_parameters["memory_id"]

        try:
            async_mode = is_async_mode(self.runtime.credentials)
            if async_mode:
                client = AsyncLocalClient(self.runtime.credentials)
                loop = AsyncLocalClient.ensure_bg_loop()
                result = asyncio.run_coroutine_threadsafe(client.get(memory_id), loop).result()
            else:
                client = LocalClient(self.runtime.credentials)
                result = client.get(memory_id)

            # Check if memory exists
            if not result or not isinstance(result, dict):
                error_message = f"Memory not found: {memory_id}"
                yield self.create_json_message(
                    {"status": "ERROR", "messages": error_message, "results": {}})
                yield self.create_text_message(f"Error: {error_message}")
                return

            yield self.create_json_message({
                "status": "SUCCESS",
                "messages": {"memory_id": memory_id},
                "results": {
                    "id": result.get("id"),
                    "memory": result.get("memory"),
                    "metadata": result.get("metadata", {}),
                    "created_at": result.get("created_at"),
                    "updated_at": result.get("updated_at", ""),
                }
            })

            text_response = (
                f"Memory Details:\n\n"
                f"ID: {result.get('id', '')}\n"
                f"Memory: {result.get('memory', '')}\n"
                f"Metadata: {result.get('metadata', {})}\n"
                f"Created: {result.get('created_at', '')}\n"
                f"Updated: {result.get('updated_at', '')}\n"
            )

            yield self.create_text_message(text_response)

        except (ValueError, RuntimeError, TypeError) as e:
            error_message = f"Error: {e!s}"
            yield self.create_json_message(
                {"status": "ERROR", "messages": error_message, "results": {}})
            yield self.create_text_message(f"Failed to get memory: {error_message}")
