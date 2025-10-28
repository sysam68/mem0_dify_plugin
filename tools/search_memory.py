"""Dify tool to package search payload for mem0 client and return results."""

import json
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from utils.mem0_client import get_mem0_client


class RetrieveMem0Tool(Tool):
    """Tool that builds a search payload and delegates to mem0_client.search."""

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        version = tool_parameters.get("version", "v1")

        # Validate required fields
        query = tool_parameters.get("query", "")
        user_id = tool_parameters.get("user_id")
        if not query:
            yield self.create_text_message("Failed to search memory: query is required")
            return
        if not user_id:
            yield self.create_text_message("Failed to search memory: user_id is required")
            return

        # Build payload
        payload: dict[str, Any] = {"query": query, "user_id": user_id}

        # Filters for v2
        filters_value = tool_parameters.get("filters")
        if version == "v2" and filters_value:
            try:
                payload["filters"] = (
                    json.loads(filters_value)
                    if isinstance(filters_value, str)
                    else filters_value
                )
                payload["version"] = "v2"
            except json.JSONDecodeError as json_err:
                msg = f"Invalid JSON in filters: {json_err}"
                yield self.create_json_message({"status": "error", "error": msg})
                yield self.create_text_message(f"Failed to search memory: {msg}")
                return
        else:
            # Optional scoping fields
            agent_id = tool_parameters.get("agent_id")
            run_id = tool_parameters.get("run_id")
            if agent_id:
                payload["agent_id"] = agent_id
            if run_id:
                payload["run_id"] = run_id

        # Optional top_k -> limit mapping for mem0_client
        if tool_parameters.get("top_k") is not None:
            try:
                payload["limit"] = int(tool_parameters.get("top_k"))
            except (TypeError, ValueError):
                payload["limit"] = tool_parameters.get("top_k")

        try:
            client = get_mem0_client(self.runtime.credentials)
            results = client.search(payload)

            # JSON output
            norm_results = []
            for r in results or []:
                if not isinstance(r, dict):
                    continue
                norm_results.append(
                    {
                        "id": r.get("id"),
                        "memory": r.get("memory"),
                        "score": r.get("score", 0.0),
                        "categories": r.get("categories", []),
                        "created_at": r.get("created_at", ""),
                    }
                )

            yield self.create_json_message({
                "query": payload.get("query", ""),
                "results": norm_results,
            })

            # Text output
            lines = [f"Query: {payload.get('query', '')}", "", "Results:"]
            if norm_results:
                for idx, r in enumerate(norm_results, 1):
                    lines.append("")
                    lines.append(f"{idx}. Memory: {r.get('memory', '')}")
                    score = r.get("score")
                    if isinstance(score, (int, float)):
                        lines.append(f"   Score: {score:.2f}")
                    cats = r.get("categories") or []
                    if cats:
                        lines.append(f"   Categories: {', '.join(cats)}")
            else:
                lines.append("")
                lines.append("No results found.")

            yield self.create_text_message("\n".join(lines))

        except json.JSONDecodeError as e:
            # Should not happen here, but guard anyway
            error_message = f"Error parsing JSON: {e}"
            yield self.create_json_message({"status": "error", "error": error_message})
            yield self.create_text_message(f"Failed to search memory: {error_message}")
        except Exception as e:  # noqa: BLE001 - surface unexpected errors
            error_message = f"Error: {e}"
            yield self.create_json_message({"status": "error", "error": error_message})
            yield self.create_text_message(f"Failed to search memory: {error_message}")
