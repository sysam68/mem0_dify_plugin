## mem0

**Author:** yevanchen
**Version:** 0.0.1
**Type:** tool

### Description

mem0 is a memory management plugin that enables conversation history storage and retrieval for LLM applications.

![workflow](./_assets/workflow.png)



### Setup

1. Get your API key from [mem0 dashboard](https://app.mem0.ai/dashboard/api-keys)
2. Install the package:
```bash
pip install mem0ai
```

3. Initialize the client:
```python
from mem0 import MemoryClient
client = MemoryClient(api_key="your-api-key")
```

![dashboard](./_assets/dashboard.png)

### Memory Actions

#### add_memory
Stores conversation history and context for users.

```python
messages = [
    {"role": "user", "content": "Hi, I'm Alex. I'm a vegetarian and I'm allergic to nuts."},
    {"role": "assistant", "content": "Hello Alex! I've noted your dietary preferences."}
]
client.add(messages, user_id="alex")
```

Backend logic:
- Messages are stored in user-specific partitions using `user_id`
- Supports conversation history and context storage
- Handles message format validation and processing
- Optimizes storage for efficient retrieval

#### search_memory
Searches relevant conversation history based on queries.

```python
query = "What can I cook for dinner tonight?"
memories = client.search(query, user_id="alex")
```

Backend logic:
- Semantic search across user's memory partition
- Returns relevant conversation snippets
- Handles context ranking and relevance scoring
- Optimizes query performance

### Usage in Dify

1. In Dify workflows, place `search_memory` before LLM calls to provide context
2. Add `add_memory` after LLM responses to store new interactions
3. `user_id` can be customized in workflow run API
4. Note: iframe and webapp modes currently don't support user_id due to lack of access control

### Maybe Future Features
- Multimodal Support
- Memory Customization
- Custom Categories & Instructions
- Direct Import
- Async Client
- Memory Export
- Webhooks
- Graph Memory
- REST API Server
- OpenAI Compatibility
- Custom Prompts

For feature requests or discussions, contact evanchen@dify.ai

