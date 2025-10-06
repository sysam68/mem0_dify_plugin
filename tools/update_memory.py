from collections.abc import Generator
from typing import Any
import httpx
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

class UpdateMemoryTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        # Get API key from credentials
        api_key = self.runtime.credentials["mem0_api_key"]
        
        # Get parameters
        memory_id = tool_parameters["memory_id"]
        text = tool_parameters["text"]
        
        # Prepare payload
        payload = {"text": text}
        
        # Make HTTP request to mem0 API
        try:
            response = httpx.put(
                f"https://api.mem0.ai/v1/memories/{memory_id}/",
                json=payload,
                headers={"Authorization": f"Token {api_key}"},
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            # Return JSON format
            yield self.create_json_message({
                "status": "success",
                "memory": {
                    "id": result["id"],
                    "memory": result["memory"],
                    "hash": result.get("hash", ""),
                    "metadata": result.get("metadata", {}),
                    "created_at": result["created_at"],
                    "updated_at": result.get("updated_at", ""),
                    "user_id": result.get("user_id"),
                    "agent_id": result.get("agent_id"),
                    "app_id": result.get("app_id"),
                    "run_id": result.get("run_id")
                }
            })
            
            # Return text format
            text_response = f"Memory updated successfully!\n\n"
            text_response += f"ID: {result['id']}\n"
            text_response += f"Updated Memory: {result['memory']}\n"
            if result.get("updated_at"):
                text_response += f"Updated At: {result['updated_at']}\n"
            
            yield self.create_text_message(text_response)
            
        except httpx.HTTPStatusError as e:
            error_message = f"HTTP error: {e.response.status_code}"
            if e.response.status_code == 404:
                error_message = f"Memory with ID '{memory_id}' not found"
            else:
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
            
            yield self.create_text_message(f"Failed to update memory: {error_message}")
            
        except Exception as e:
            error_message = f"Error: {str(e)}"
            
            yield self.create_json_message({
                "status": "error",
                "error": error_message
            })
            
            yield self.create_text_message(f"Failed to update memory: {error_message}")
