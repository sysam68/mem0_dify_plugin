"""Mem0 provider for Dify plugin system.

This module implements a tool provider for Mem0, a memory system that supports
both SaaS and local operation modes. The provider handles credential validation
and provides an interface for Dify to interact with Mem0's memory capabilities.
"""

from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError
from utils.mem0_client import get_mem0_client


class Mem0Provider(ToolProvider):
    """Tool provider for Mem0; validates credentials for SaaS and local modes.

    This provider validates the following credentials:
    - mode: Determines the operation mode ('SaaS' or 'local')
    - mem0_api_key: API key for SaaS mode authentication
    - For local mode: simplified JSON configs for LLM/Embedder/Reranker/Vector/Graph

    The validation process performs a lightweight check to ensure connectivity
    and proper authentication with the selected Mem0 service.
    """

    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            mode = (credentials.get("mode") or "SaaS").lower()
            client = get_mem0_client(credentials)

            if mode == "saas":
                # Minimal search to validate API key
                _ = client.search({"query": "test", "user_id": "validation_test"})
            else:
                # Local mode: sanity check by performing a no-op search
                _ = client.search({"query": "test", "user_id": "validation_test"})
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e)) from e
