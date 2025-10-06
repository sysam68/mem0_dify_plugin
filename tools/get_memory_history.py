from collections.abc import Generator
from typing import Any
import httpx
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

class GetMemoryHistoryTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        # Get API key from credentials
        api_key = self.runtime.credentials["mem0_api_key"]
        
        # Get memory ID
        memory_id = tool_parameters["memory_id"]
        
        # Make HTTP request to mem0 API
        try:
            response = httpx.get(
                f"https://api.mem0.ai/v1/memories/{memory_id}/history/",
                headers={"Authorization": f"Token {api_key}"},
                timeout=30
            )
            response.raise_for_status()
            results = response.json()
            
            # Return JSON format
            yield self.create_json_message({
                "status": "success",
                "memory_id": memory_id,
                "history_count": len(results),
                "history": [{
                    "id": h["id"],
                    "memory_id": h["memory_id"],
                    "prev_value": h.get("prev_value"),
                    "new_value": h.get("new_value"),
                    "event": h.get("event"),
                    "timestamp": h.get("timestamp"),
                    "is_deleted": h.get("is_deleted", False)
                } for h in results]
            })
            
            # Return text format
            text_response = f"Memory History for ID: {memory_id}\n\n"
            text_response += f"Total changes: {len(results)}\n\n"
            
            if results:
                for idx, h in enumerate(results, 1):
                    text_response += f"{idx}. Event: {h.get('event', 'N/A')}\n"
                    if h.get("prev_value"):
                        text_response += f"   Previous: {h['prev_value']}\n"
                    if h.get("new_value"):
                        text_response += f"   New: {h['new_value']}\n"
                    if h.get("timestamp"):
                        text_response += f"   Timestamp: {h['timestamp']}\n"
                    text_response += "\n"
            else:
                text_response += "No history found for this memory."
            
            yield self.create_text_message(text_response)
            
        except httpx.HTTPStatusError as e:
            error_message = f"HTTP error: {e.response.status_code}"
            if e.response.status_code == 404:
                error_message = f"Memory with ID '{memory_id}' not found or has no history"
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
            
            yield self.create_text_message(f"Failed to get memory history: {error_message}")
            
        except Exception as e:
            error_message = f"Error: {str(e)}"
            
            yield self.create_json_message({
                "status": "error",
                "error": error_message
            })
            
            yield self.create_text_message(f"Failed to get memory history: {error_message}")
