from collections.abc import Generator
from typing import Any
import httpx
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

class GetAllMemoriesTool(Tool):
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
        if tool_parameters.get("limit"):
            params["limit"] = int(tool_parameters["limit"])
        
        # Make HTTP request to mem0 API
        try:
            response = httpx.get(
                "https://api.mem0.ai/v1/memories/",
                params=params,
                headers={"Authorization": f"Token {api_key}"},
                timeout=30
            )
            response.raise_for_status()
            results = response.json()
            
            # Return JSON format
            yield self.create_json_message({
                "status": "success",
                "count": len(results),
                "memories": [{
                    "id": r["id"],
                    "memory": r["memory"],
                    "hash": r.get("hash", ""),
                    "metadata": r.get("metadata", {}),
                    "created_at": r["created_at"],
                    "updated_at": r.get("updated_at", ""),
                    "user_id": r.get("user_id"),
                    "agent_id": r.get("agent_id"),
                    "app_id": r.get("app_id"),
                    "run_id": r.get("run_id")
                } for r in results]
            })
            
            # Return text format
            text_response = f"Found {len(results)} memories\n\n"
            if results:
                for idx, r in enumerate(results, 1):
                    text_response += f"{idx}. {r['memory']}\n"
                    text_response += f"   ID: {r['id']}\n"
                    if r.get("user_id"):
                        text_response += f"   User ID: {r['user_id']}\n"
                    if r.get("agent_id"):
                        text_response += f"   Agent ID: {r['agent_id']}\n"
                    if r.get("app_id"):
                        text_response += f"   App ID: {r['app_id']}\n"
                    if r.get("metadata"):
                        text_response += f"   Metadata: {r['metadata']}\n"
                    text_response += f"   Created: {r['created_at']}\n\n"
            else:
                text_response += "No memories found."
            
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
            
            yield self.create_text_message(f"Failed to get memories: {error_message}")
            
        except Exception as e:
            error_message = f"Error: {str(e)}"
            
            yield self.create_json_message({
                "status": "error",
                "error": error_message
            })
            
            yield self.create_text_message(f"Failed to get memories: {error_message}")
