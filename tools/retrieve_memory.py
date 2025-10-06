from collections.abc import Generator
from typing import Any, Dict, List
import json
import httpx
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

class RetrieveMem0Tool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        # Get API key from credentials
        api_key = self.runtime.credentials["mem0_api_key"]
        
        # Get version (default to v1)
        version = tool_parameters.get("version", "v1")
        
        # Prepare payload for search
        payload = {
            "query": tool_parameters["query"]
        }
        
        # Handle different API versions
        if version == "v2" and tool_parameters.get("filters"):
            # v2 API with advanced filters
            try:
                filters = json.loads(tool_parameters["filters"])
                payload["filters"] = filters
            except json.JSONDecodeError as e:
                yield self.create_json_message({
                    "status": "error",
                    "error": f"Invalid JSON in filters: {str(e)}"
                })
                yield self.create_text_message(f"Failed to retrieve memory: Invalid JSON in filters: {str(e)}")
                return
        else:
            # v1 API or v2 without filters - use simple ID parameters
            if tool_parameters.get("user_id"):
                payload["user_id"] = tool_parameters["user_id"]
            if tool_parameters.get("agent_id"):
                payload["agent_id"] = tool_parameters["agent_id"]
            if tool_parameters.get("app_id"):
                payload["app_id"] = tool_parameters["app_id"]
            if tool_parameters.get("run_id"):
                payload["run_id"] = tool_parameters["run_id"]
        
        # Add limit if provided
        if tool_parameters.get("limit"):
            payload["limit"] = int(tool_parameters["limit"])
        
        # Add version to payload if v2
        if version == "v2":
            payload["version"] = "v2"
        
        # Make direct HTTP request to mem0 API
        try:
            response = httpx.post(
                "https://api.mem0.ai/v1/memories/search/",
                json=payload,
                headers={"Authorization": f"Token {api_key}"},
                timeout=30
            )
            response.raise_for_status()
            results = response.json()
            
            # Return JSON format
            yield self.create_json_message({
                "query": tool_parameters["query"],
                "results": [{
                    "id": r["id"],
                    "memory": r["memory"],
                    "score": r["score"],
                    "categories": r.get("categories", []),
                    "created_at": r["created_at"]
                } for r in results]
            })
            
            # Return text format
            text_response = f"Query: {tool_parameters['query']}\n\nResults:\n"
            if results:
                for idx, r in enumerate(results, 1):
                    text_response += f"\n{idx}. Memory: {r['memory']}"
                    text_response += f"\n   Score: {r['score']:.2f}"
                    text_response += f"\n   Categories: {', '.join(r.get('categories', []))}"
            else:
                text_response += "\nNo results found."
                
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
            
            yield self.create_text_message(f"Failed to retrieve memory: {error_message}")
            
        except Exception as e:
            error_message = f"Error: {str(e)}"
            
            yield self.create_json_message({
                "status": "error",
                "error": error_message
            })
            
            yield self.create_text_message(f"Failed to retrieve memory: {error_message}")
