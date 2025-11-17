import asyncio
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from utils.config_builder import is_async_mode
from utils.constants import DELETE_ALL_ACCEPT_RESULT
from utils.mem0_client import AsyncLocalClient, LocalClient


class DeleteAllMemoriesTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        # Build params
        params: dict[str, Any] = {}
        if tool_parameters.get("user_id"):
            params["user_id"] = tool_parameters["user_id"]
        if tool_parameters.get("agent_id"):
            params["agent_id"] = tool_parameters["agent_id"]
        if tool_parameters.get("run_id"):
            params["run_id"] = tool_parameters["run_id"]

        # Validate at least one identifier
        if not any([params.get("user_id"), params.get("agent_id"), params.get("run_id")]):
            error_message = "At least one of user_id, agent_id, or run_id must be provided"
            yield self.create_json_message(
                {"status": "ERROR", "messages": error_message, "results": []})
            yield self.create_text_message(f"Error: {error_message}")
            return

        try:
            async_mode = is_async_mode(self.runtime.credentials)
            if async_mode:
                client = AsyncLocalClient(self.runtime.credentials)
                # Submit delete_all to background event loop without awaiting (non-blocking)
                loop = AsyncLocalClient.ensure_bg_loop()
                asyncio.run_coroutine_threadsafe(client.delete_all(params), loop)

                yield self.create_json_message({
                    "status": "SUCCESS",
                    "messages": {"filters": params},
                    **DELETE_ALL_ACCEPT_RESULT,
                })
                yield self.create_text_message(
                    "Asynchronous batch memory deletion has been accepted.")
            else:
                client = LocalClient(self.runtime.credentials)
                result = client.delete_all(params)
                yield self.create_json_message({
                    "status": "SUCCESS",
                    "messages": {"filters": params},
                    "results": result,
                })
                yield self.create_text_message(
                    f"All memories deleted successfully with filters : {params}")

        except (ValueError, RuntimeError, TypeError) as e:
            error_message = f"Error: {e!s}"
            yield self.create_json_message(
                {"status": "ERROR", "messages": error_message, "results": []})
            yield self.create_text_message(f"Failed to delete memories: {error_message}")
