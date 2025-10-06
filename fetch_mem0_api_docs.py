#!/usr/bin/env python3
"""
Manually create Mem0 API documentation based on known endpoints
"""

import os
import json
from datetime import datetime

# Directory to save docs
DOCS_DIR = "mem0-api-docs"
os.makedirs(DOCS_DIR, exist_ok=True)

# Known Mem0 API endpoints based on documentation
API_ENDPOINTS = {
    "add-memories": {
        "title": "Add Memories",
        "method": "POST",
        "endpoint": "/v1/memories/",
        "description": "Add memories to Mem0",
        "headers": {
            "Authorization": "Token <your-api-key>",
            "Content-Type": "application/json"
        },
        "body_params": {
            "messages": "list[dict] - List of message objects with role and content",
            "user_id": "string (optional) - User identifier",
            "agent_id": "string (optional) - Agent identifier", 
            "app_id": "string (optional) - App identifier",
            "run_id": "string (optional) - Run identifier",
            "metadata": "dict (optional) - Additional metadata",
            "filters": "dict (optional) - Filters to apply",
            "prompt": "string (optional) - Custom prompt for fact extraction"
        },
        "example_request": """curl -X POST "https://api.mem0.ai/v1/memories/" \\
  -H "Authorization: Token your-api-key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "Hi, my name is Alice and I love hiking."
      },
      {
        "role": "assistant", 
        "content": "Nice to meet you Alice! Hiking is a great activity. Do you have any favorite trails?"
      }
    ],
    "user_id": "alice123"
  }'""",
        "response": {
            "success": True,
            "message": "Memories added successfully",
            "memories": ["List of created memory objects"]
        }
    },
    
    "get-memories": {
        "title": "Get Memories",
        "method": "GET",
        "endpoint": "/v1/memories/",
        "description": "Retrieve memories from Mem0",
        "headers": {
            "Authorization": "Token <your-api-key>"
        },
        "query_params": {
            "user_id": "string (optional) - Filter by user",
            "agent_id": "string (optional) - Filter by agent",
            "app_id": "string (optional) - Filter by app",
            "run_id": "string (optional) - Filter by run",
            "limit": "integer (optional) - Number of memories to return",
            "offset": "integer (optional) - Pagination offset"
        },
        "example_request": """curl -X GET "https://api.mem0.ai/v1/memories/?user_id=alice123" \\
  -H "Authorization: Token your-api-key" """,
        "response": {
            "memories": ["Array of memory objects"],
            "total": "Total number of memories",
            "limit": "Current limit",
            "offset": "Current offset"
        }
    },
    
    "get-all-memories": {
        "title": "Get All Memories", 
        "method": "GET",
        "endpoint": "/v1/memories/",
        "description": "Retrieve all memories without filters",
        "headers": {
            "Authorization": "Token <your-api-key>"
        },
        "query_params": {
            "limit": "integer (optional, default=100) - Number of memories per page",
            "offset": "integer (optional, default=0) - Pagination offset"
        },
        "example_request": """curl -X GET "https://api.mem0.ai/v1/memories/" \\
  -H "Authorization: Token your-api-key" """,
        "example_paginated": """# Get first 100 memories
curl -X GET "https://api.mem0.ai/v1/memories/?limit=100&offset=0" \\
  -H "Authorization: Token your-api-key"
  
# Get next 100 memories  
curl -X GET "https://api.mem0.ai/v1/memories/?limit=100&offset=100" \\
  -H "Authorization: Token your-api-key" """,
        "response": {
            "memories": [
                {
                    "id": "memory-id",
                    "memory": "Memory content",
                    "hash": "unique-hash",
                    "metadata": {},
                    "created_at": "timestamp",
                    "updated_at": "timestamp",
                    "user_id": "user-id"
                }
            ],
            "total": "Total number of memories",
            "limit": 100,
            "offset": 0
        }
    },
    
    "search-memories": {
        "title": "Search Memories",
        "method": "POST", 
        "endpoint": "/v1/memories/search/",
        "description": "Search memories using semantic search",
        "headers": {
            "Authorization": "Token <your-api-key>",
            "Content-Type": "application/json"
        },
        "body_params": {
            "query": "string (required) - Search query",
            "user_id": "string (optional) - Filter by user",
            "agent_id": "string (optional) - Filter by agent",
            "app_id": "string (optional) - Filter by app",
            "run_id": "string (optional) - Filter by run",
            "limit": "integer (optional, default=10) - Number of results",
            "filters": "dict (optional) - Additional filters"
        },
        "example_request": """curl -X POST "https://api.mem0.ai/v1/memories/search/" \\
  -H "Authorization: Token your-api-key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "hiking trails",
    "user_id": "alice123",
    "limit": 5
  }'""",
        "response": {
            "results": ["Array of matching memories with relevance scores"]
        }
    },
    
    "update-memory": {
        "title": "Update Memory",
        "method": "PUT",
        "endpoint": "/v1/memories/{memory_id}/",
        "description": "Update an existing memory",
        "headers": {
            "Authorization": "Token <your-api-key>",
            "Content-Type": "application/json"
        },
        "body_params": {
            "data": "string (required) - New memory content"
        },
        "example_request": """curl -X PUT "https://api.mem0.ai/v1/memories/memory-id-123/" \\
  -H "Authorization: Token your-api-key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "data": "Updated memory content"
  }'""",
        "response": {
            "success": True,
            "message": "Memory updated successfully"
        }
    },
    
    "delete-memory": {
        "title": "Delete Memory",
        "method": "DELETE", 
        "endpoint": "/v1/memories/{memory_id}/",
        "description": "Delete a specific memory",
        "headers": {
            "Authorization": "Token <your-api-key>"
        },
        "example_request": """curl -X DELETE "https://api.mem0.ai/v1/memories/memory-id-123/" \\
  -H "Authorization: Token your-api-key" """,
        "response": {
            "success": True,
            "message": "Memory deleted successfully"
        }
    },
    
    "delete-all-memories": {
        "title": "Delete All Memories",
        "method": "DELETE",
        "endpoint": "/v1/memories/",
        "description": "Delete all memories for specific entities",
        "headers": {
            "Authorization": "Token <your-api-key>",
            "Content-Type": "application/json"
        },
        "body_params": {
            "user_id": "string (optional) - Delete all memories for user",
            "agent_id": "string (optional) - Delete all memories for agent",
            "app_id": "string (optional) - Delete all memories for app",
            "run_id": "string (optional) - Delete all memories for run"
        },
        "example_request": """curl -X DELETE "https://api.mem0.ai/v1/memories/" \\
  -H "Authorization: Token your-api-key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "user_id": "alice123"
  }'""",
        "response": {
            "success": True,
            "message": "Memories deleted successfully"
        }
    }
}

def create_markdown_doc(endpoint_key, endpoint_data):
    """Create markdown documentation for an endpoint"""
    
    md_content = f"""---
source: https://api.mem0.ai{endpoint_data['endpoint']}
title: {endpoint_data['title']}
date_created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

# {endpoint_data['title']}

{endpoint_data['description']}

## Endpoint

```
{endpoint_data['method']} {endpoint_data['endpoint']}
```

## Headers

```json
{json.dumps(endpoint_data['headers'], indent=2)}
```

"""
    
    # Add body parameters if applicable
    if 'body_params' in endpoint_data:
        md_content += "## Request Body Parameters\n\n"
        for param, desc in endpoint_data['body_params'].items():
            md_content += f"- **{param}**: {desc}\n"
        md_content += "\n"
    
    # Add query parameters if applicable
    if 'query_params' in endpoint_data:
        md_content += "## Query Parameters\n\n"
        for param, desc in endpoint_data['query_params'].items():
            md_content += f"- **{param}**: {desc}\n"
        md_content += "\n"
    
    # Add example request
    md_content += "## Example Request\n\n```bash\n"
    md_content += endpoint_data['example_request']
    md_content += "\n```\n\n"
    
    # Add additional examples if present
    if 'example_paginated' in endpoint_data:
        md_content += "### Pagination Example\n\n```bash\n"
        md_content += endpoint_data['example_paginated']
        md_content += "\n```\n\n"
    
    # Add response format
    md_content += "## Response Format\n\n```json\n"
    md_content += json.dumps(endpoint_data['response'], indent=2)
    md_content += "\n```\n"
    
    # Save to file
    filename = f"{endpoint_key}.md"
    filepath = os.path.join(DOCS_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"Created: {filepath}")

def create_index():
    """Create an index file"""
    index_content = """# Mem0 API Documentation

This directory contains the API documentation for Mem0's core memory operations.

## Available Endpoints

### Memory Operations

1. **[Add Memories](add-memories.md)** - Add new memories to Mem0
2. **[Get Memories](get-memories.md)** - Retrieve memories with filters
3. **[Get All Memories](get-all-memories.md)** - Retrieve all memories without filters
4. **[Search Memories](search-memories.md)** - Search memories using semantic search
5. **[Update Memory](update-memory.md)** - Update an existing memory
6. **[Delete Memory](delete-memory.md)** - Delete a specific memory
7. **[Delete All Memories](delete-all-memories.md)** - Delete all memories for specific entities

## Authentication

All API requests require authentication using an API key:

```bash
-H "Authorization: Token <your-api-key>"
```

## Base URL

```
https://api.mem0.ai
```

## Rate Limits

Please refer to the official documentation for current rate limit information.

## Support

For support and additional documentation, visit:
- Documentation: https://docs.mem0.ai
- GitHub: https://github.com/mem0ai/mem0
"""
    
    with open(os.path.join(DOCS_DIR, "README.md"), 'w', encoding='utf-8') as f:
        f.write(index_content)
    
    print(f"Created index: {os.path.join(DOCS_DIR, 'README.md')}")

def main():
    """Generate API documentation"""
    print("Generating Mem0 API documentation...")
    
    # Create documentation for each endpoint
    for endpoint_key, endpoint_data in API_ENDPOINTS.items():
        create_markdown_doc(endpoint_key, endpoint_data)
    
    # Create index
    create_index()
    
    print(f"\nDocumentation complete! Files saved in: {os.path.abspath(DOCS_DIR)}")

if __name__ == "__main__":
    main()
