## User Guide of how to develop a Dify Plugin

Hi there, looks like you have already created a Plugin, now let's get you started with the development!

### Choose a Plugin type you want to develop

Before start, you need some basic knowledge about the Plugin types, Plugin supports to extend the following abilities in Dify:
- **Tool**: Tool Providers like Google Search, Stable Diffusion, etc. it can be used to perform a specific task.
- **Model**: Model Providers like OpenAI, Anthropic, etc. you can use their models to enhance the AI capabilities.
- **Endpoint**: Like Service API in Dify and Ingress in Kubernetes, you can extend a http service as an endpoint and control its logics using your own code.

Based on the ability you want to extend, we have divided the Plugin into three types: **Tool**, **Model**, and **Extension**.

- **Tool**: It's a tool provider, but not only limited to tools, you can implement an endpoint there, for example, you need both `Sending Message` and `Receiving Message` if you are building a Discord Bot, **Tool** and **Endpoint** are both required.
- **Model**: Just a model provider, extending others is not allowed.
- **Extension**: Other times, you may only need a simple http service to extend the functionalities, **Extension** is the right choice for you.

I believe you have chosen the right type for your Plugin while creating it, if not, you can change it later by modifying the `manifest.yaml` file.

### Manifest

Now you can edit the `manifest.yaml` file to describe your Plugin, here is the basic structure of it:

- version(version, required)：Plugin's version
- type(type, required)：Plugin's type, currently only supports `plugin`, future support `bundle`
- author(string, required)：Author, it's the organization name in Marketplace and should also equals to the owner of the repository
- label(label, required)：Multi-language name
- created_at(RFC3339, required)：Creation time, Marketplace requires that the creation time must be less than the current time
- icon(asset, required)：Icon path
- resource (object)：Resources to be applied
  - memory (int64)：Maximum memory usage, mainly related to resource application on SaaS for serverless, unit bytes
  - permission(object)：Permission application
    - tool(object)：Reverse call tool permission
      - enabled (bool)
    - model(object)：Reverse call model permission
      - enabled(bool)
      - llm(bool)
      - text_embedding(bool)
      - rerank(bool)
      - tts(bool)
      - speech2text(bool)
      - moderation(bool)
    - node(object)：Reverse call node permission
      - enabled(bool) 
    - endpoint(object)：Allow to register endpoint permission
      - enabled(bool)
    - app(object)：Reverse call app permission
      - enabled(bool)
    - storage(object)：Apply for persistent storage permission
      - enabled(bool)
      - size(int64)：Maximum allowed persistent memory, unit bytes
- plugins(object, required)：Plugin extension specific ability yaml file list, absolute path in the plugin package, if you need to extend the model, you need to define a file like openai.yaml, and fill in the path here, and the file on the path must exist, otherwise the packaging will fail.
  - Format
    - tools(list[string]): Extended tool suppliers, as for the detailed format, please refer to [Tool Guide](https://docs.dify.ai/docs/plugins/standard/tool_provider)
    - models(list[string])：Extended model suppliers, as for the detailed format, please refer to [Model Guide](https://docs.dify.ai/docs/plugins/standard/model_provider)
    - endpoints(list[string])：Extended Endpoints suppliers, as for the detailed format, please refer to [Endpoint Guide](https://docs.dify.ai/docs/plugins/standard/endpoint_group)
  - Restrictions
    - Not allowed to extend both tools and models
    - Not allowed to have no extension
    - Not allowed to extend both models and endpoints
    - Currently only supports up to one supplier of each type of extension
- meta(object)
  - version(version, required)：manifest format version, initial version 0.0.1
  - arch(list[string], required)：Supported architectures, currently only supports amd64 arm64
  - runner(object, required)：Runtime configuration
    - language(string)：Currently only supports python
    - version(string)：Language version, currently only supports 3.12
    - entrypoint(string)：Program entry, in python it should be main

### Install Dependencies

- First of all, you need a Python 3.10+ environment, as our SDK requires that.
- Then, install the dependencies:
    ```bash
    pip install -r requirements.txt
    ```
- If you want to add more dependencies, you can add them to the `requirements.txt` file, once you have set the runner to python in the `manifest.yaml` file, `requirements.txt` will be automatically generated and used for packaging and deployment.

### Implement the Plugin

Now you can start to implement your Plugin, by following these examples, you can quickly understand how to implement your own Plugin:

- [OpenAI](https://github.com/langgenius/dify-plugin-sdks/tree/main/python/examples/openai): best practice for model provider
- [Google Search](https://github.com/langgenius/dify-plugin-sdks/tree/main/python/examples/google): a simple example for tool provider
- [Neko](https://github.com/langgenius/dify-plugin-sdks/tree/main/python/examples/neko): a funny example for endpoint group

### Test and Debug the Plugin

You may already noticed that a `.env.example` file in the root directory of your Plugin, just copy it to `.env` and fill in the corresponding values, there are some environment variables you need to set if you want to debug your Plugin locally.

- `INSTALL_METHOD`: Set this to `remote`, your plugin will connect to a Dify instance through the network.
- `REMOTE_INSTALL_HOST`: The host of your Dify instance, you can use our SaaS instance `https://debug.dify.ai`, or self-hosted Dify instance.
- `REMOTE_INSTALL_PORT`: The port of your Dify instance, default is 5003
- `REMOTE_INSTALL_KEY`: You should get your debugging key from the Dify instance you used, at the right top of the plugin management page, you can see a button with a `debug` icon, click it and you will get the key.

Run the following command to start your Plugin:

```bash
python -m main
```

Refresh the page of your Dify instance, you should be able to see your Plugin in the list now, but it will be marked as `debugging`, you can use it normally, but not recommended for production.

### Package the Plugin

After all, just package your Plugin by running the following command:

```bash
dify-plugin plugin package ./ROOT_DIRECTORY_OF_YOUR_PLUGIN
```

you will get a `plugin.difypkg` file, that's all, you can submit it to the Marketplace now, look forward to your Plugin being listed!


### Plugin-specific configuration (Mem0 Dify Plugin)

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
    - Search Memory: 60 seconds
    - Get All Memories: 60 seconds
    - Get Memory: 30 seconds
    - Get Memory History: 30 seconds
  
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
  - `SEARCH_DEFAULT_TOP_K`, `MAX_CONCURRENT_MEM_ADDS`, `MAX_REQUEST_TIMEOUT`
  - `SEARCH_OPERATION_TIMEOUT` (60s), `GET_OPERATION_TIMEOUT` (30s), `GET_ALL_OPERATION_TIMEOUT` (60s), `HISTORY_OPERATION_TIMEOUT` (30s)
  - `ADD_SKIP_RESULT`, `ADD_ACCEPT_RESULT`, `UPDATE_ACCEPT_RESULT`, `DELETE_ACCEPT_RESULT`, `DELETE_ALL_ACCEPT_RESULT`
  - `CUSTOM_PROMPT` for memory extraction

### Async mode switch
- `async_mode` is a provider credential (boolean) and defaults to true
- When `async_mode=true` (default):
  - Write operations (Add/Update/Delete/Delete_All): non-blocking, return ACCEPT status immediately
  - Read operations (Search/Get/Get_All/History): wait for results with timeout protection (60s for Search/Get_All, 30s for Get/History)
- When `async_mode=false`:
  - All operations block until completion

### Timeout & Service Degradation (v0.1.1+)
- **Timeout Values**:
  - Search Memory: 60 seconds
  - Get All Memories: 60 seconds
  - Get Memory: 30 seconds
  - Get Memory History: 30 seconds
- **Service Degradation**: When operations timeout or encounter errors:
  - The event is logged with full exception details using `logger.exception`
  - Background tasks are cancelled using `future.cancel()` to prevent resource leaks
  - Default/empty results are returned (empty list `[]` for Search/Get_All/History, `None` for Get)
  - Dify workflow continues execution without interruption
- **Error Handling**: All tools now catch all `Exception` types, not just specific ones, ensuring comprehensive error coverage

### Important operational notes

#### Delete All Memories Operation
> **Note**: When using the `delete_all_memories` tool to delete memories in batch, Mem0 will automatically reset the vector index to optimize performance and reclaim space. You may see a log message like `WARNING: Resetting index mem0...` during this operation. This is a **normal and expected behavior** — the warning indicates that the vector store table is being dropped and recreated to ensure optimal query performance after bulk deletion. No action is needed from your side.

#### Vector Store Connection
- **Debug Mode** (running `python -m main` locally): Use `localhost:<port>` to connect to pgvector
- **Production Mode** (running in Docker): Use Docker container name (e.g., `docker-pgvector-1`) and internal port (e.g., `5432`)

## User Privacy Policy

Please fill in the privacy policy of the plugin if you want to make it published on the Marketplace, refer to [PRIVACY.md](PRIVACY.md) for more details.