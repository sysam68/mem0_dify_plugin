# Mem0 Dify Plugin v0.0.3

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Dify Plugin](https://img.shields.io/badge/Dify-Plugin-blue)](https://dify.ai)
[![Mem0 AI](https://img.shields.io/badge/Mem0-AI-green)](https://mem0.ai)

A comprehensive Dify plugin that integrates [Mem0 AI](https://mem0.ai)'s intelligent memory layer, providing **8 powerful tools** with full **API v2 support** including advanced filtering, metadata, and multi-entity management.

![Dashboard](./_assets/dashboard.png)

---

## 🌟 Features

### Complete Memory Management (8 Tools)
- ✅ **Add Memory** - Create memories with metadata and multi-entity support
- ✅ **Retrieve Memory** - Search with v2 advanced filters (AND/OR logic)
- ✅ **Get All Memories** - List memories with pagination
- ✅ **Get Memory** - Fetch specific memory details
- ✅ **Update Memory** - Modify existing memories
- ✅ **Delete Memory** - Remove individual memories
- ✅ **Delete All Memories** - Batch delete with filters
- ✅ **Get Memory History** - View change history

### Advanced Capabilities
- 🚀 **Mem0 API v2** - Full support with advanced filters
- 🎯 **Multi-Entity Support** - user_id, agent_id, app_id, run_id
- 📊 **Metadata System** - Custom JSON metadata for rich context
- 🔍 **Complex Filters** - AND/OR logic for precise queries
- 🌍 **Internationalized** - 4 languages (en/zh/pt/ja)
- ♻️ **100% Backward Compatible** - Works with existing workflows

---

## 🚀 Quick Start

### Method 1: Install from GitHub (Recommended)

1. **In Dify Dashboard**
   - Go to `Settings` → `Plugins`
   - Click `Install from GitHub`
   - Enter your repository URL
   - Click `Install`

2. **Configure API Key**
   - Get your API key from [Mem0 Dashboard](https://app.mem0.ai/dashboard/api-keys)
   - Enter it in the plugin settings

3. **Start Using**
   - All 8 tools are now available in your workflows!

### Method 2: Install from Package

Download `mem0-0.0.3.difypkg` from [Releases](../../releases) and upload it manually in Dify.

---

## 📖 Usage Examples

### Basic Usage

#### Add a Memory
```json
{
  "user": "I love Italian food",
  "assistant": "Great! I'll remember that.",
  "user_id": "alex"
}
```

#### Search Memories
```json
{
  "query": "What food does alex like?",
  "user_id": "alex"
}
```

### Advanced v2 Features

#### Add Memory with Metadata
```json
{
  "user": "I prefer morning meetings",
  "assistant": "Noted!",
  "user_id": "alex",
  "agent_id": "scheduler",
  "metadata": "{\"type\": \"preference\", \"priority\": \"high\"}"
}
```

#### Search with Advanced Filters
```json
{
  "query": "user preferences",
  "version": "v2",
  "filters": "{\"AND\": [{\"user_id\": \"alex\"}, {\"agent_id\": \"scheduler\"}]}"
}
```

#### Get All Memories for an Agent
```json
{
  "agent_id": "travel_assistant",
  "limit": 50
}
```

---

## 🛠️ Available Tools

| Tool | Description | v2 Support |
|------|-------------|-----------|
| `add_mem0ai_memory` | Add new memories with metadata | ✅ |
| `retrieve_mem0ai_memory` | Search with advanced filters | ✅ |
| `get_all_mem0ai_memories` | List all memories | ✅ |
| `get_mem0ai_memory` | Get specific memory | ✅ |
| `update_mem0ai_memory` | Update memory content | ✅ |
| `delete_mem0ai_memory` | Delete single memory | ✅ |
| `delete_all_mem0ai_memories` | Batch delete memories | ✅ |
| `get_mem0ai_memory_history` | View change history | ✅ |

---

## 📚 Documentation

- **[CHANGELOG.md](CHANGELOG.md)** - Detailed changelog and examples
- **[INSTALL.md](INSTALL.md)** - Installation guide
- **[BUGFIX.md](BUGFIX.md)** - Known issues and fixes
- **[Mem0 Official Docs](https://docs.mem0.ai)** - Full API documentation

---

## 🎯 Use Cases

### Personal Assistant
```python
# Remember user preferences
add_memory("I prefer morning meetings", user_id="john")
add_memory("I'm vegetarian", user_id="john")

# Query preferences
search("when does john prefer meetings?", user_id="john")
```

### Customer Support
```python
# Track interactions
add_memory("Customer reported login issue", user_id="customer_123")

# Retrieve context
search("previous issues", user_id="customer_123")
```

### Multi-Agent Systems
```python
# Agent-specific memories
add_memory("User likes Italian food", agent_id="food_agent")
add_memory("User prefers Rome", agent_id="travel_agent")

# Search across agents
search("user preferences", 
       version="v2",
       filters='{"OR": [{"agent_id": "food_agent"}, {"agent_id": "travel_agent"}]}')
```

---

## 🔧 Configuration

### Requirements
- Dify instance (self-hosted or cloud)
- Mem0 API key ([Get one here](https://app.mem0.ai/dashboard/api-keys))
- Python 3.12+ (for local development)

### Environment Variables (for development)
```bash
MEM0_API_KEY=your_api_key_here
```

---

## 🚀 Development

### Local Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/dify-plugin-mem0.git
   cd dify-plugin-mem0
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run locally**
   ```bash
   python -m main
   ```

### Testing

Run YAML validation:
```bash
for file in tools/*.yaml; do 
  python3 -c "import yaml; yaml.safe_load(open('$file'))" && echo "✅ $(basename $file)"
done
```

---

## 📊 Version History

| Version | Date | Changes |
|---------|------|---------|
| v0.0.3 | 2025-10-06 | Added 6 new tools, v2 API support, metadata, multi-entity |
| v0.0.2 | 2025-02-24 | Basic add and retrieve functionality |
| v0.0.1 | Initial | First release |

See [CHANGELOG.md](CHANGELOG.md) for detailed changes.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [Dify](https://dify.ai) - AI application development platform
- [Mem0 AI](https://mem0.ai) - Intelligent memory layer for AI
- Built with ❤️ using Dify Plugin SDK

---

## 📞 Support

- **Issues**: [GitHub Issues](../../issues)
- **Documentation**: [Mem0 Docs](https://docs.mem0.ai)
- **Dify Docs**: [Plugin Development](https://docs.dify.ai/docs/plugins)

---

## ⭐ Show Your Support

If you find this plugin useful, please give it a ⭐ on GitHub!

---

**Made with ❤️ by yevanchen**
