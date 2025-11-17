import asyncio
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from utils.config_builder import is_async_mode
from utils.mem0_client import AsyncLocalClient, LocalClient


class GetMemoryHistoryTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        memory_id = tool_parameters["memory_id"]

        try:
            async_mode = is_async_mode(self.runtime.credentials)
            if async_mode:
                client = AsyncLocalClient(self.runtime.credentials)
                loop = AsyncLocalClient.ensure_bg_loop()
                results = asyncio.run_coroutine_threadsafe(client.history(memory_id), loop).result()
            else:
                client = LocalClient(self.runtime.credentials)
                results = client.history(memory_id)

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
            error_message = f"Error: {e!s}"
            yield self.create_json_message(
                {"status": "ERROR", "messages": error_message, "results": []})
            yield self.create_text_message(f"Failed to get memory history: {error_message}")
