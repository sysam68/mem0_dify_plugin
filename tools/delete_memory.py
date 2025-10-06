from collections.abc import Generator
from typing import Any
import httpx
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

class DeleteMemoryTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        # Get API key from credentials
        api_key = self.runtime.credentials["mem0_api_key"]
        
        # Get memory ID
        memory_id = tool_parameters["memory_id"]
        
        # Make HTTP request to mem0 API
        try:
            response = httpx.delete(
                f"https://api.mem0.ai/v1/memories/{memory_id}/",
                headers={"Authorization": f"Token {api_key}"},
                timeout=30
            )
            response.raise_for_status()
            
            # Return JSON format
            yield self.create_json_message({
                "status": "success",
                "message": f"Memory '{memory_id}' deleted successfully",
                "memory_id": memory_id
            })
            
            # Return text format
            yield self.create_text_message(f"Memory deleted successfully!\n\nDeleted Memory ID: {memory_id}")
            
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
            
            yield self.create_text_message(f"Failed to delete memory: {error_message}")
            
        except Exception as e:
            error_message = f"Error: {str(e)}"
            
            yield self.create_json_message({
                "status": "error",
                "error": error_message
            })
            
            yield self.create_text_message(f"Failed to delete memory: {error_message}")
