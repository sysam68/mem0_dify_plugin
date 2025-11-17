# Mem0 Dify Plugin - Changelog

## Version 0.0.9 (2025-11-17)

### 🎯 Unified Return Format & Enhanced Async Operations

This release focuses on standardizing tool outputs and extending non-blocking async behavior to all write operations.

#### Highlights
- **Unified JSON Return Structure**:
  - All tools now return consistent format: `{"status": "SUCCESS/ERROR", "messages": {...}, "results": {...}}`
  - `status`: Operation status (SUCCESS or ERROR)
  - `messages`: Context information (query params, filters, IDs, etc.)
  - `results`: Actual data (memories, history, operation results)
  
- **Enhanced Async Operations**:
  - Write operations (Add/Update/Delete/Delete_All) are now non-blocking in async mode
  - Return ACCEPT messages immediately: `UPDATE_ACCEPT_RESULT`, `DELETE_ACCEPT_RESULT`, `DELETE_ALL_ACCEPT_RESULT`
  - Read operations (Search/Get/Get_All/History) always wait for results
  
- **Standardized Return Fields**:
  - Search/Get/Get_All: `id`, `memory`, `metadata`, `created_at`, `updated_at`
  - History: `memory_id`, `old_memory`, `new_memory`, `event`, `created_at`, `updated_at`, `is_deleted`
  - Removed redundant fields: `hash`, `user_id`, `agent_id`, `run_id` from individual memory objects
  
- **Extended Constants** (`utils/constants.py`):
  - Added `UPDATE_ACCEPT_RESULT`: `{"message": "Memory update has been accepted"}`
  - Added `DELETE_ACCEPT_RESULT`: `{"message": "Memory deletion has been accepted"}`
  - Added `DELETE_ALL_ACCEPT_RESULT`: `{"message": "Batch memory deletion has been accepted"}`
  
- **Complete Documentation**:
  - All methods in `LocalClient` and `AsyncLocalClient` now have comprehensive docstrings
  - Consistent parameter descriptions and return value documentation
  - Clear async vs sync behavior documentation

#### Technical Details
- **Async Mode Behavior**:
  - When `async_mode=true` (default):
    - Add/Update/Delete/Delete_All: Submit to background loop without waiting, return ACCEPT status
    - Search/Get/Get_All/History: Wait for results via `asyncio.run_coroutine_threadsafe().result()`
  - When `async_mode=false`:
    - All operations use `LocalClient` and block until completion
    
- **Error Handling**:
  - All error responses include `"results": []` for consistency
  - Exception types unified: `(ValueError, RuntimeError, TypeError)`

#### Migration Notes
- Tool outputs now use `status` instead of `event` for top-level status indicator
- If your workflow parses tool outputs, update to use the new field names
- Async write operations now return ACCEPT messages instead of actual results

---

## Version 0.0.8 (2025-11-11)

- Add async_mode provider credential (default true) with clear runtime behavior
- Tools route to LocalClient/AsyncLocalClient based on async_mode for all operations
- Provider validation aligns with async_mode
- Docs updated (README/INSTALL/GUIDE/manifest) to reflect async vs sync behavior

## Version 0.0.7 (2025-11-08)

### 🚀 Local-only, async client, graceful shutdown

This release focuses on stability, local-only operation, and developer ergonomics.

#### Highlights
- Centralized constants in `utils/constants.py`:
  - `MAX_CONCURRENT_MEM_ADDS` (default: 5)
  - `SEARCH_DEFAULT_TOP_K` (default: 5)
  - `MAX_REQUEST_TIMEOUT` (default: 120)
  - Shared response shapes: `ADD_SKIP_RESULT`, `ADD_ACCEPT_RESULT`
  - `CUSTOM_PROMPT` for memory distillation (optional)
- Background event loop:
  - Single process-wide loop created once and reused
  - Tools dispatch async operations via `asyncio.run_coroutine_threadsafe(...)`
- Graceful shutdown:
  - `AsyncLocalClient.shutdown()` drains pending tasks briefly and stops the loop
  - Registered via `atexit` and SIGTERM/SIGINT in `main.py`
- Non-blocking add:
  - `AddMem0Tool` enqueues add and returns immediately with `{"status": "queued", ...}`
  - Skips empty/blank messages with `{"status": "skipped", "reason": "no messages", ...}`
- Search improvements:
  - Executes on the background loop
  - Returns normalized JSON and a detailed text message for downstream nodes

#### Removals/Cleanups
- SaaS mode and API version parameters removed
- Deprecated `run_async_task` and background task tracking removed
- Input validation for empty messages centralized in tool layer

---

## Version 0.0.3 (2025-10-05)

### 🎉 Major Update: Full Mem0 API v2 Support

This version brings complete support for Mem0's latest API features, including v2 advanced filtering and full CRUD operations.

---

## ✨ New Features

### 📦 6 New Tools Added

1. **Get All Memories** (`get_all_memories`)
   - Retrieve all memories for a user, agent, app, or run
   - Supports pagination with limit parameter
   - Multi-entity filtering support

2. **Get Memory** (`get_memory`)
   - Fetch a specific memory by its ID
   - Returns complete memory details including metadata

3. **Update Memory** (`update_memory`)
   - Update existing memory content
   - Preserves memory metadata and entity associations

4. **Delete Memory** (`delete_memory`)
   - Delete a specific memory by ID
   - Safe deletion with confirmation

5. **Delete All Memories** (`delete_all_memories`)
   - Batch delete memories by entity filters
   - Requires at least one entity ID for safety

6. **Get Memory History** (`get_memory_history`)
   - View complete change history of a memory
   - Shows previous and new values for each change

---

## 🔄 Enhanced Existing Tools

### **Add Memory** (Enhanced)
**New Parameters:**
- `agent_id` - Associate memory with an agent
- `app_id` - Associate memory with an application
- `run_id` - Associate memory with a specific run
- `metadata` - Custom metadata as JSON string
- `output_format` - Choose between v1.0, v1.1, or v2 output formats

**Breaking Changes:**
- `user_id` is now optional (at least one entity ID should be provided)

### **Retrieve Memory** (Enhanced with v2 API)
**New Parameters:**
- `version` - Select API version (v1 or v2)
- `agent_id` - Filter by agent ID
- `app_id` - Filter by application ID
- `run_id` - Filter by run ID
- `filters` - Advanced AND/OR logic filters (v2 only)
- `limit` - Maximum number of results

**v2 Advanced Filters Example:**
```json
{
  "AND": [
    {"user_id": "alex"},
    {
      "OR": [
        {"agent_id": "travel_agent"},
        {"agent_id": "food_agent"}
      ]
    }
  ]
}
```

---

## 🌟 Key Improvements

### Multi-Entity Support
All tools now support multiple entity types:
- `user_id` - User-specific memories
- `agent_id` - Agent-specific memories
- `app_id` - Application-specific memories
- `run_id` - Run-specific memories

### Metadata Support
- Add custom metadata when creating memories
- Retrieve and filter by metadata
- Supports any JSON-serializable data

### Version Control
- Choose output format (v1.0/v1.1/v2)
- v2 provides richer response data
- Backward compatible with v1

### Enhanced Error Handling
- Better error messages for invalid JSON
- Clear validation for required parameters
- HTTP status code specific error handling

---

## 📋 Complete Tool List

### Memory Management (8 Tools)
1. ✅ Add Memory - Create new memories
2. ✅ Search Memory - Search memories with advanced filters
3. ✅ Get All Memories - List all memories
4. ✅ Get Memory - Get single memory details
5. ✅ Update Memory - Modify existing memories
6. ✅ Delete Memory - Remove single memory
7. ✅ Delete All Memories - Batch delete memories
8. ✅ Get Memory History - View memory change history

---

## 🔧 Technical Details

### API Endpoints Covered
- `POST /v1/memories/` - Create memories
- `POST /v1/memories/search/` - Search memories (v1 & v2)
- `GET /v1/memories/` - List memories
- `GET /v1/memories/{id}/` - Get memory
- `PUT /v1/memories/{id}/` - Update memory
- `DELETE /v1/memories/{id}/` - Delete memory
- `DELETE /v1/memories/` - Batch delete
- `GET /v1/memories/{id}/history/` - Memory history

### Dependencies
- `httpx` - HTTP client
- `dify_plugin` - Dify plugin framework
- Python 3.12

### Configuration Updates
- Updated `provider/mem0.yaml` with all 8 tools
- Updated `manifest.yaml` to version 0.0.3
- Enhanced tool descriptions with v2 features

---

## 🌍 Internationalization

All new features include complete translations:
- 🇺🇸 English (en_US)
- 🇨🇳 Simplified Chinese (zh_Hans)
- 🇧🇷 Portuguese (pt_BR)
- 🇯🇵 Japanese (ja_JP)

---

## 🚀 Migration Guide

### From v0.0.2 to v0.0.3

**Breaking Changes:**
1. `user_id` in `add_memory` is now optional
   - **Action**: Ensure at least one of `user_id`, `agent_id`, `app_id`, or `run_id` is provided

2. `user_id` in `search_memory` is now optional
   - **Action**: Can use `filters` or other entity IDs instead

**Recommended Updates:**
1. Start using `metadata` for richer context
2. Migrate to v2 API for advanced filtering
3. Use entity IDs to organize memories by context

**Backward Compatibility:**
- All v0.0.2 workflows continue to work
- No code changes required for existing implementations
- New parameters are optional

---

## 📚 Usage Examples

### Example 1: Add Memory with Metadata
```json
{
  "user": "I love Italian food",
  "assistant": "Great! I'll remember that.",
  "user_id": "alex",
  "agent_id": "food_assistant",
  "metadata": "{\"category\": \"food_preferences\", \"cuisine\": \"italian\"}"
}
```

### Example 2: Advanced Search with v2 Filters
```json
{
  "query": "What are my food preferences?",
  "version": "v2",
  "filters": "{\"AND\": [{\"user_id\": \"alex\"}, {\"agent_id\": \"food_assistant\"}]}"
}
```

### Example 3: Get All Memories for an Agent
```json
{
  "agent_id": "travel_assistant",
  "limit": 50
}
```

---

## 🐛 Bug Fixes
- Fixed JSON parsing errors with better error messages
- Improved HTTP status code handling
- Enhanced validation for required parameters

---

## 📝 Notes

- All API calls use 30-second timeout
- JSON responses include both structured data and human-readable text
- Supports all Mem0 Platform features as of October 2025

---

## 🙏 Credits

- Based on [Mem0 AI](https://mem0.ai) official API documentation
- Developed using Context7 for documentation retrieval
- Compatible with Dify Plugin Framework

---

## 📞 Support

For issues or questions:
- Check the official [Mem0 Documentation](https://docs.mem0.ai)
- Review the tool YAML files for parameter details
- Test with Dify Plugin Debugger

---

**Full Changelog**: v0.0.2 → v0.0.3
