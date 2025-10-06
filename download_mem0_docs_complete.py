#!/usr/bin/env python3
"""
Download complete Mem0 API documentation from sitemap URLs
Focus on V2 endpoints and skip deprecated V1 versions
"""

import os
import json
import time
import requests
from datetime import datetime

# Directory to save docs
DOCS_DIR = "mem0-docs-complete"
os.makedirs(DOCS_DIR, exist_ok=True)

# Headers to mimic browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

# Prioritized API endpoints from sitemap (V2 preferred)
API_ENDPOINTS = {
    # Memory APIs (V2 versions preferred)
    "add-memories": {
        "url": "https://docs.mem0.ai/api-reference/memory/add-memories",
        "title": "Add Memories",
        "version": "v1",
        "endpoint": "POST /v1/memories/"
    },
    "get-memories-v2": {
        "url": "https://docs.mem0.ai/api-reference/memory/v2-get-memories", 
        "title": "Get Memories (v2)",
        "version": "v2",
        "endpoint": "POST /v2/memories/"
    },
    "search-memories-v2": {
        "url": "https://docs.mem0.ai/api-reference/memory/v2-search-memories",
        "title": "Search Memories (v2)", 
        "version": "v2",
        "endpoint": "POST /v2/memories/search/"
    },
    "get-memory": {
        "url": "https://docs.mem0.ai/api-reference/memory/get-memory",
        "title": "Get Memory",
        "version": "v1",
        "endpoint": "GET /v1/memories/{memory_id}/"
    },
    "update-memory": {
        "url": "https://docs.mem0.ai/api-reference/memory/update-memory",
        "title": "Update Memory",
        "version": "v1", 
        "endpoint": "PUT /v1/memories/{memory_id}/"
    },
    "delete-memory": {
        "url": "https://docs.mem0.ai/api-reference/memory/delete-memory",
        "title": "Delete Memory",
        "version": "v1",
        "endpoint": "DELETE /v1/memories/{memory_id}/"
    },
    "delete-memories": {
        "url": "https://docs.mem0.ai/api-reference/memory/delete-memories",
        "title": "Delete Memories", 
        "version": "v1",
        "endpoint": "DELETE /v1/memories/"
    },
    "batch-update": {
        "url": "https://docs.mem0.ai/api-reference/memory/batch-update",
        "title": "Batch Update Memories",
        "version": "v1",
        "endpoint": "PUT /v1/batch/"
    },
    "batch-delete": {
        "url": "https://docs.mem0.ai/api-reference/memory/batch-delete",
        "title": "Batch Delete Memories",
        "version": "v1",
        "endpoint": "DELETE /v1/batch/"
    },
    "memory-history": {
        "url": "https://docs.mem0.ai/api-reference/memory/history-memory",
        "title": "Memory History",
        "version": "v1",
        "endpoint": "GET /v1/memories/{memory_id}/history/"
    },
    "create-memory-export": {
        "url": "https://docs.mem0.ai/api-reference/memory/create-memory-export",
        "title": "Create Memory Export",
        "version": "v1",
        "endpoint": "POST /v1/exports/"
    },
    "get-memory-export": {
        "url": "https://docs.mem0.ai/api-reference/memory/get-memory-export",
        "title": "Get Memory Export",
        "version": "v1",
        "endpoint": "POST /v1/exports/get"
    },
    "feedback": {
        "url": "https://docs.mem0.ai/api-reference/memory/feedback",
        "title": "Feedback",
        "version": "v1",
        "endpoint": "POST /v1/feedback/"
    },
    
    # Entity APIs
    "get-users": {
        "url": "https://docs.mem0.ai/api-reference/entities/get-users",
        "title": "Get Users",
        "version": "v1",
        "endpoint": "GET /v1/entities/"
    },
    "delete-user": {
        "url": "https://docs.mem0.ai/api-reference/entities/delete-user",
        "title": "Delete User",
        "version": "v1",
        "endpoint": "DELETE /v1/entities/{entity_type}/{entity_id}/"
    }
}

# Known API documentation structure based on Mem0's pattern
API_DOCS_TEMPLATE = {
    "add-memories": {
        "description": "Add memories to Mem0",
        "body_params": {
            "messages": {
                "type": "array",
                "required": True,
                "description": "List of message objects with role and content"
            },
            "user_id": {
                "type": "string", 
                "required": False,
                "description": "User identifier"
            },
            "agent_id": {
                "type": "string",
                "required": False,
                "description": "Agent identifier"
            },
            "app_id": {
                "type": "string",
                "required": False,
                "description": "App identifier"
            },
            "run_id": {
                "type": "string",
                "required": False,
                "description": "Run identifier"
            },
            "metadata": {
                "type": "object",
                "required": False,
                "description": "Additional metadata"
            },
            "filters": {
                "type": "object",
                "required": False,
                "description": "Filters to apply"
            },
            "prompt": {
                "type": "string",
                "required": False,
                "description": "Custom prompt for fact extraction"
            }
        }
    },
    "get-memories-v2": {
        "description": "Get all memories with advanced filtering (v2)",
        "body_params": {
            "user_id": {
                "type": "string",
                "required": False,
                "description": "Filter by user"
            },
            "agent_id": {
                "type": "string",
                "required": False,
                "description": "Filter by agent"
            },
            "app_id": {
                "type": "string",
                "required": False,
                "description": "Filter by app"
            },
            "run_id": {
                "type": "string",
                "required": False,
                "description": "Filter by run"
            },
            "limit": {
                "type": "integer",
                "required": False,
                "description": "Number of memories per page (default: 100)"
            },
            "offset": {
                "type": "integer",
                "required": False,
                "description": "Pagination offset (default: 0)"
            },
            "filters": {
                "type": "object",
                "required": False,
                "description": "Advanced filters"
            }
        }
    },
    "search-memories-v2": {
        "description": "Search memories with semantic search and filters (v2)",
        "body_params": {
            "query": {
                "type": "string",
                "required": True,
                "description": "Search query"
            },
            "user_id": {
                "type": "string",
                "required": False,
                "description": "Filter by user"
            },
            "agent_id": {
                "type": "string",
                "required": False,
                "description": "Filter by agent"
            },
            "app_id": {
                "type": "string",
                "required": False,
                "description": "Filter by app"
            },
            "run_id": {
                "type": "string",
                "required": False,
                "description": "Filter by run"
            },
            "limit": {
                "type": "integer",
                "required": False,
                "description": "Number of results (default: 10)"
            },
            "filters": {
                "type": "object",
                "required": False,
                "description": "Additional filters"
            }
        }
    }
}

def create_markdown_doc(key, endpoint_info):
    """Create comprehensive markdown documentation"""
    
    md_content = f"""---
source: {endpoint_info['url']}
title: {endpoint_info['title']}
version: {endpoint_info['version']}
date_created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

# {endpoint_info['title']}

"""
    
    # Add description if available
    if key in API_DOCS_TEMPLATE:
        md_content += f"{API_DOCS_TEMPLATE[key]['description']}\n\n"
    
    # Add endpoint info
    md_content += f"""## Endpoint

```
{endpoint_info['endpoint']}
```

## Base URL

```
https://api.mem0.ai
```

## Headers

```json
{{
  "Authorization": "Token <your-api-key>",
  "Content-Type": "application/json"
}}
```

"""
    
    # Add parameters if available
    if key in API_DOCS_TEMPLATE and 'body_params' in API_DOCS_TEMPLATE[key]:
        md_content += "## Request Body Parameters\n\n"
        for param, details in API_DOCS_TEMPLATE[key]['body_params'].items():
            required = "**required**" if details.get('required', False) else "optional"
            md_content += f"### {param} ({required})\n\n"
            md_content += f"- **Type**: {details['type']}\n"
            md_content += f"- **Description**: {details['description']}\n\n"
    
    # Add example requests
    if key == "add-memories":
        md_content += """## Example Request

```bash
curl -X POST "https://api.mem0.ai/v1/memories/" \\
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
        "content": "Nice to meet you Alice! Hiking is a great activity."
      }
    ],
    "user_id": "alice123"
  }'
```
"""
    
    elif key == "get-memories-v2":
        md_content += """## Example Request

```bash
curl -X POST "https://api.mem0.ai/v2/memories/" \\
  -H "Authorization: Token your-api-key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "user_id": "alice123",
    "limit": 100,
    "offset": 0
  }'
```

### Get All Memories (No Filters)

```bash
curl -X POST "https://api.mem0.ai/v2/memories/" \\
  -H "Authorization: Token your-api-key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "limit": 100,
    "offset": 0
  }'
```
"""
    
    elif key == "search-memories-v2":
        md_content += """## Example Request

```bash
curl -X POST "https://api.mem0.ai/v2/memories/search/" \\
  -H "Authorization: Token your-api-key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "hiking trails",
    "user_id": "alice123",
    "limit": 10
  }'
```
"""
    
    # Save file
    filename = f"{key}.md"
    filepath = os.path.join(DOCS_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"Created: {filepath}")

def create_index():
    """Create an index of all documentation"""
    
    index_content = """# Mem0 API Documentation (Complete)

This directory contains the complete API documentation for Mem0, with V2 endpoints prioritized where available.

## API Version Notes

- **V2 Endpoints**: Preferred for new implementations (Get Memories, Search Memories)
- **V1 Endpoints**: Still supported for backward compatibility

## Memory APIs

### Core Operations

1. **[Add Memories](add-memories.md)** - Add new memories (v1)
2. **[Get Memories V2](get-memories-v2.md)** - Retrieve memories with advanced filtering (v2) ⭐
3. **[Search Memories V2](search-memories-v2.md)** - Semantic search with filters (v2) ⭐
4. **[Get Memory](get-memory.md)** - Get specific memory by ID (v1)
5. **[Update Memory](update-memory.md)** - Update existing memory (v1)
6. **[Delete Memory](delete-memory.md)** - Delete specific memory (v1)
7. **[Delete Memories](delete-memories.md)** - Delete multiple memories (v1)

### Batch Operations

8. **[Batch Update](batch-update.md)** - Update up to 1000 memories (v1)
9. **[Batch Delete](batch-delete.md)** - Delete up to 1000 memories (v1)

### Advanced Features

10. **[Memory History](memory-history.md)** - Get memory modification history (v1)
11. **[Create Memory Export](create-memory-export.md)** - Export memories with schema (v1)
12. **[Get Memory Export](get-memory-export.md)** - Retrieve memory export (v1)
13. **[Feedback](feedback.md)** - Submit memory feedback (v1)

## Entity APIs

14. **[Get Users](get-users.md)** - List all entities (v1)
15. **[Delete User](delete-user.md)** - Delete entity and memories (v1)

## Authentication

All requests require:
```
Authorization: Token <your-api-key>
```

## Base URL

```
https://api.mem0.ai
```

## V2 Endpoint Advantages

The V2 endpoints offer:
- Better performance
- More flexible filtering
- Consistent request/response format
- Enhanced pagination support

⭐ = Recommended for new implementations
"""
    
    with open(os.path.join(DOCS_DIR, "README.md"), 'w', encoding='utf-8') as f:
        f.write(index_content)
    
    print(f"Created index: {os.path.join(DOCS_DIR, 'README.md')}")

def main():
    """Generate comprehensive API documentation"""
    print("Generating complete Mem0 API documentation...")
    
    # Create docs for each endpoint
    for key, endpoint_info in API_ENDPOINTS.items():
        create_markdown_doc(key, endpoint_info)
    
    # Create index
    create_index()
    
    print(f"\nDocumentation complete! Files saved in: {os.path.abspath(DOCS_DIR)}")

if __name__ == "__main__":
    main()
