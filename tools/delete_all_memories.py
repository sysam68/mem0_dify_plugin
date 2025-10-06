from collections.abc import Generator
from typing import Any
import httpx
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

class DeleteAllMemoriesTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        # Get API key from credentials
        api_key = self.runtime.credentials["mem0_api_key"]
        
        # Build query parameters
        params = {}
        
        # Check at least one ID is provided
        if not any([
            tool_parameters.get("user_id"),
            tool_parameters.get("agent_id"),
            tool_parameters.get("app_id"),
            tool_parameters.get("run_id")
        ]):
            error_message = "At least one of user_id, agent_id, app_id, or run_id must be provided"
            yield self.create_json_message({
                "status": "error",
                "error": error_message
            })
            yield self.create_text_message(f"Error: {error_message}")
            return
        
        # Add optional parameters
        if tool_parameters.get("user_id"):
            params["user_id"] = tool_parameters["user_id"]
        if tool_parameters.get("agent_id"):
            params["agent_id"] = tool_parameters["agent_id"]
        if tool_parameters.get("app_id"):
            params["app_id"] = tool_parameters["app_id"]
        if tool_parameters.get("run_id"):
            params["run_id"] = tool_parameters["run_id"]
        
        # Make HTTP request to mem0 API
        try:
            response = httpx.delete(
                "https://api.mem0.ai/v1/memories/",
                params=params,
                headers={"Authorization": f"Token {api_key}"},
                timeout=30
            )
            response.raise_for_status()
            
            # Return JSON format
            yield self.create_json_message({
                "status": "success",
                "message": "All memories deleted successfully",
                "filters": params
            })
            
            # Return text format
            text_response = "All memories deleted successfully!\n\nFilters applied:\n"
            for key, value in params.items():
                text_response += f"- {key}: {value}\n"
            
            yield self.create_text_message(text_response)
            
        except httpx.HTTPStatusError as e:
            error_message = f"HTTP error: {e.response.status_code}"
            try:
                error_data = e.response.json()
                if "detail" in error_data:
                    error_message = f"Error: {error_data['detail']}"
            except:
                pass
            
            yield self.create_json_message({
                "status": "error",
                "error": error_message
            })
            
            yield self.create_text_message(f"Failed to delete memories: {error_message}")
            
        except Exception as e:
            error_message = f"Error: {str(e)}"
            
            yield self.create_json_message({
                "status": "error",
                "error": error_message
            })
            
            yield self.create_text_message(f"Failed to delete memories: {error_message}")
