# Mem0 Dify Plugin - Developer Guide

This guide provides technical details for developers working with the Mem0 Dify Plugin.

## Plugin Configuration (Mem0 Dify Plugin)

This plugin runs in Local mode only. Provider credentials are:

- Required (JSON objects):
  - `local_llm_json`
  - `local_embedder_json`
  - `local_vector_db_json` (e.g., pgvector or pinecone)
- Optional:
  - `local_graph_db_json` (Neo4j)
  - `local_reranker_json`

Each JSON must be a map with shape: `{ "provider": <string>, "config": { ... } }`.

### Runtime behavior (important)

- **Asynchronous execution**:
  - Tools submit async coroutines to a single process-wide background event loop
  - Write operations (Add/Update/Delete/Delete_All) are non-blocking: return ACCEPT status immediately
  - Read operations (Search/Get/Get_All/History) wait for results and return actual data
  - **Timeout protection** (v0.1.1+): All async read operations have timeout mechanisms:
    - Search Memory: 30 seconds (default, configurable in v0.1.2+)
    - Get All Memories: 30 seconds (default, configurable in v0.1.2+)
    - Get Memory: 30 seconds (default, configurable in v0.1.2+)
    - Get Memory History: 30 seconds (default, configurable in v0.1.2+)
  
- **Service degradation** (v0.1.1+):
  - When operations timeout or encounter errors, the plugin gracefully degrades:
    - Logs the event with full exception details
    - Cancels background tasks using `future.cancel()` to prevent resource leaks
    - Returns default/empty results (empty list `[]` for Search/Get_All/History, `None` for Get)
    - Ensures Dify workflow continues execution without interruption
  
- **Unified return format**:
  - All tools return: `{"status": "SUCCESS/ERROR", "messages": {...}, "results": {...}}`
  - Write ops in async mode return ACCEPT results: `UPDATE_ACCEPT_RESULT`, `DELETE_ACCEPT_RESULT`, etc.
  
- **Graceful shutdown**:
  - The plugin registers an exit hook and SIGTERM/SIGINT handlers to drain pending tasks briefly and stop the background loop
  
- **Constants** (`utils/constants.py`):
  - `SEARCH_DEFAULT_TOP_K`, `MAX_CONCURRENT_MEM_ADDS`, `MAX_REQUEST_TIMEOUT` (60s in v0.1.2+)
  - `SEARCH_OPERATION_TIMEOUT` (30s in v0.1.2+), `GET_OPERATION_TIMEOUT` (30s), `GET_ALL_OPERATION_TIMEOUT` (30s in v0.1.2+), `HISTORY_OPERATION_TIMEOUT` (30s)
  - `ADD_SKIP_RESULT`, `ADD_ACCEPT_RESULT`, `UPDATE_ACCEPT_RESULT`, `DELETE_ACCEPT_RESULT`, `DELETE_ALL_ACCEPT_RESULT`
  - `CUSTOM_PROMPT` for memory extraction

### Async mode switch
- `async_mode` is a provider credential (boolean) and defaults to true
- When `async_mode=true` (default):
  - Write operations (Add/Update/Delete/Delete_All): non-blocking, return ACCEPT status immediately
  - Read operations (Search/Get/Get_All/History): wait for results with timeout protection (30s for all operations in v0.1.2+)
- When `async_mode=false`:
  - All operations block until completion
  - **Note**: Sync mode has no timeout protection (blocking calls). If timeout protection is needed, use `async_mode=true`

### Timeout & Service Degradation (v0.1.1+)
- **Configurable Timeout** (v0.1.2+):
  - All read operations (Search/Get/Get_All/History) support user-configurable timeout values
  - Timeout parameters are available in the Dify plugin configuration interface as manual input fields
  - If not specified, tools use default values from `constants.py`
  - Invalid timeout values are caught and logged with a warning, defaulting to constants

- **Default Timeout Values** (v0.1.2+):
  - Search Memory: 30 seconds (reduced from 60s)
  - Get All Memories: 30 seconds (reduced from 60s)
  - Get Memory: 30 seconds
  - Get Memory History: 30 seconds
  - `MAX_REQUEST_TIMEOUT`: 60 seconds (reduced from 120s)
  - **Note**: Sync mode has no timeout protection (blocking calls). If timeout protection is needed, use `async_mode=true`
- **Service Degradation**: When operations timeout or encounter errors:
  - The event is logged with full exception details using `logger.exception`
  - Background tasks are cancelled using `future.cancel()` to prevent resource leaks (async mode only)
  - Default/empty results are returned (empty list `[]` for Search/Get_All/History, `None` for Get)
  - Dify workflow continues execution without interruption
- **Unified Exception Handling**: Both sync and async modes have unified exception handling:
  - Async mode: Handles `FuturesTimeoutError` (timeout) and general `Exception` types
  - Sync mode: Handles general `Exception` types only (no timeout exceptions)
  - Both modes implement service degradation to ensure workflow continuity

### Important operational notes

#### Delete All Memories Operation
> **Note**: When using the `delete_all_memories` tool to delete memories in batch, Mem0 will automatically reset the vector index to optimize performance and reclaim space. You may see a log message like `WARNING: Resetting index mem0...` during this operation. This is a **normal and expected behavior** — the warning indicates that the vector store table is being dropped and recreated to ensure optimal query performance after bulk deletion. No action is needed from your side.

#### Vector Store Connection
- **Debug Mode** (running `python -m main` locally): Use `localhost:<port>` to connect to pgvector
- **Production Mode** (running in Docker): Use Docker container name (e.g., `docker-pgvector-1`) and internal port (e.g., `5432`)

## User Privacy Policy

Please fill in the privacy policy of the plugin if you want to make it published on the Marketplace, refer to [PRIVACY.md](PRIVACY.md) for more details.