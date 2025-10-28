"""Dify tool for adding a memory via Mem0 client."""

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from utils.mem0_client import get_mem0_client


class Mem0Tool(Tool):
    """Tool to add user/assistant messages as a memory."""

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        # Required user_id
        user_id = tool_parameters.get("user_id")
        if not user_id:
            error_message = "user_id is required"
            yield self.create_json_message({"status": "error", "error": error_message})
            yield self.create_text_message(f"Failed to add memory: {error_message}")
            return

        # Collect inputs
        user_text = tool_parameters.get("user", "")
        assistant_text = tool_parameters.get("assistant", "")
        agent_id = tool_parameters.get("agent_id")
        app_id = tool_parameters.get("app_id")
        run_id = tool_parameters.get("run_id")
        metadata = tool_parameters.get("metadata")  # client parses JSON if string
        output_format = tool_parameters.get("output_format")

        # Build messages
        messages = []
        if user_text:
            messages.append({"role": "user", "content": user_text})
        if assistant_text:
            messages.append({"role": "assistant", "content": assistant_text})

        # Build payload (only include optional fields if provided)
        payload: dict[str, Any] = {"messages": messages, "user_id": user_id}
        if agent_id:
            payload["agent_id"] = agent_id
        if app_id:
            payload["app_id"] = app_id
        if run_id:
            payload["run_id"] = run_id
        if metadata:
            payload["metadata"] = metadata
        if output_format:
            payload["output_format"] = output_format

        try:
            client = get_mem0_client(self.runtime.credentials)
            result = client.add(payload)

            yield self.create_json_message({
                "status": "success",
                "messages": messages,
                "result": result,
            })

            text_response = "Memory added successfully\n\nAdded messages:\n"
            for m in messages:
                text_response += f"- {m['role']}: {m['content']}\n"
            yield self.create_text_message(text_response)

        except (ValueError, RuntimeError, TypeError) as e:
            error_message = f"Error: {e!s}"
            yield self.create_json_message({"status": "error", "error": error_message})
            yield self.create_text_message(f"Failed to add memory: {error_message}")
