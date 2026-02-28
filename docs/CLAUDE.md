# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Multi-Library RAG Platform** - A general-purpose RAG (Retrieval-Augmented Generation) training and deployment platform. It supports managing multiple independent document libraries, providing both REST API and MCP SSE interfaces for AI Agent integration.

**Key Components:**
- **RAG API**: FastAPI service on port 8000 for multi-library document queries
- **MCP SSE Server**: SSE transport on port 8001 for Claude Desktop/Code integration
- **Library Manager**: Manages multiple document libraries with independent configurations
- **Vector Database**: ChromaDB with multi-collection support (one collection per library)
- **LLM**: Ollama + Qwen2.5:7b (runs on host, accessed via localhost:11434)

## Development Commands

### Local Development (without Docker)

```bash
# Start RAG API service
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Start MCP SSE server
python3 mcp_server_sse.py

# Run tests
pytest                           # All tests
pytest tests/test_api.py         # API tests only
pytest tests/test_retriever.py   # Retriever tests
pytest -v -k "test_health"       # Run specific test

# Quick test
./bin/quick_test.sh
```

### Docker Development

```bash
# Build and start all services
docker-compose build
docker-compose up -d

# View logs
docker-compose logs -f rag-api
docker-compose logs -f mcp-sse

# Stop services
docker-compose down

# Restart services
docker-compose restart
```

### Data Migration

```bash
# Migrate existing HarmonyOS data to new format
docker-compose exec rag-api python scripts/migrate_harmonyos.py
```

### Testing API Endpoints

```bash
# Health check
curl http://localhost:8000/api/v1/health

# List libraries
curl http://localhost:8000/api/v1/libraries

# Query with library_id
curl -X POST "http://localhost:8000/api/v1/query?library_id=harmonyos" \
  -H "Content-Type: application/json" \
  -d '{"query": "长时任务需要什么权限", "context_length": 5}'

# Index a library
curl -X POST http://localhost:8000/api/v1/libraries/harmonyos/index

# Export library data
curl -X POST http://localhost:8000/api/v1/libraries/harmonyos/export \
  -H "Content-Type: application/json" \
  -d '{"format": "json", "include_embeddings": true}'

# MCP SSE health check
curl http://localhost:8001/health
```

## Architecture

### Multi-Library Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     API Layer                                │
│  /api/v1/libraries  |  /api/v1/query  |  /api/v1/health   │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                  LibraryManager                              │
│  - Load config from YAML                                     │
│  - Manage library lifecycle                                  │
│  - Global indexing lock (serial)                             │
│  - Lazy-load enabled libraries only                          │
└─────────────────────────────────────────────────────────────┘
                            │
┌──────────────────┬──────────────────┬──────────────────────┐
│   VectorStore    │    Parser        │     Exporter         │
│  (Multi-collection│  (Plugin system) │  (Data portability)  │
│   per library)    │                  │                      │
└──────────────────┴──────────────────┴──────────────────────┘
```

### Key Modules

**core/library_manager.py** - Central library management
- `load_config()`: Load libraries from `data/libraries/config.yaml`
- `list_libraries()`: Get all or enabled libraries
- `set_active_library()`: Set default library for queries
- `acquire_index_lock()`: Global lock for serial indexing

**core/vector_store.py** - Multi-collection ChromaDB wrapper
- `get_collection(library_id)`: Get/create collection for specific library
- `list_collections()`: List all library collections
- `migrate_collection(old, new)`: Migrate between collections
- Lazy loading: Collections loaded on-demand

**core/models.py** - Data models for library configuration
- `LibraryConfig`: Per-library settings (embedding, chunking, metadata)
- `LibraryType`: HARMONY_OS, GENERIC_MARKDOWN, GENERIC_PDF, CUSTOM
- `LibraryStatus`: INITIALIZING, READY, INDEXING, ERROR, ARCHIVED

**core/parsers/** - Plugin architecture for document parsers
- `base.py`: BaseParser abstract class
- `harmonyos.py`: HarmonyOS-specific parser (extracts Kit, Subsystem, Owner)
- `generic.py`: Generic Markdown parser
- `get_parser(library_type)`: Factory function

**core/exporter.py** - Data export for migration
- `export_library()`: Export to JSON format
- `import_library()`: Import from exported data
- Supports embedding vectors and metadata

**core/config.py** - YAML configuration loader
- `load()`: Load from `data/libraries/config.yaml`
- `save()`: Save configuration
- Auto-detects and migrates existing HarmonyOS setup

### API Routes

**api/routes/libraries.py** - Library management
- `GET /api/v1/libraries`: List all libraries
- `POST /api/v1/libraries`: Create new library
- `GET /api/v1/libraries/{id}`: Get library details
- `DELETE /api/v1/libraries/{id}`: Delete library
- `POST /api/v1/libraries/{id}/index`: Trigger indexing
- `GET /api/v1/libraries/{id}/stats`: Get statistics
- `POST /api/v1/libraries/{id}/export`: Export data
- `GET /api/v1/libraries/active`: Get active library
- `POST /api/v1/libraries/active`: Set active library

**api/routes/query.py** - Query endpoints
- `POST /api/v1/query?library_id={id}`: Query specific library
- `POST /api/v1/query/stream`: Streaming response
- `POST /api/v1/batch_query`: Batch queries

### Configuration

**data/libraries/config.yaml** - Library configuration:

```yaml
libraries:
  harmonyos:
    id: harmonyos
    name: "HarmonyOS应用开发文档"
    type: harmony_os
    enabled: true
    source_path: "/path/to/docs"
    embedding_config:
      model_name: "BAAI/bge-base-zh-v1.5"
      device: "cpu"
    chunking_config:
      chunk_size: 1200
      chunk_overlap: 200

global:
  default_library: "harmonyos"
  max_concurrent_indexing: 1  # Serial indexing
  embedding_device: "cpu"
```

**.env** - Environment variables:
- `LIBRARIES_CONFIG_PATH`: Path to config YAML
- `DEFAULT_LIBRARY`: Default library for queries
- `EMBEDDING_DEVICE`: `cpu` or `cuda`
- `OLLAMA_BASE_URL`: Default `http://localhost:11434`

### Data Flow

1. **Configuration Loading**:
   - On startup, `LibraryManager` loads `config.yaml`
   - Only `enabled: true` libraries are loaded into memory
   - Each library has independent ChromaDB collection

2. **Query Processing**:
   - If `library_id` specified → use that library's collection
   - If not specified → use active/default library
   - Query expansion + hybrid retrieval works per-library

3. **Indexing**:
   - Global lock ensures only one library indexes at a time
   - Parser extracts library-specific metadata
   - Chunks and embeddings stored in library's collection

### MCP Tools

The MCP SSE server provides these tools:

1. **rag_query(query, library_id, context_length)**: Query a library
2. **list_libraries()**: List all libraries with status
3. **get_library_stats(library_id)**: Get library statistics

### Claude Code MCP Configuration

**Remote Access** (Windows → Linux):

Windows config: `%APPDATA%\Claude\claude_desktop_config.json`
```json
{
  "mcpServers": {
    "rag-server": {
      "type": "sse",
      "url": "http://<LINUX_IP>:8001/sse"
    }
  }
}
```

Replace `<LINUX_IP>` with your Linux server IP address.

**Usage in Claude Code**:
- `@rag_query 长时任务需要什么权限`
- `@list_libraries`
- `@get_library_stats library_id=harmonyos`

### Resource Optimization

**Serial Indexing**: Global lock ensures one library at a time
- Prevents CPU/memory spikes
- `max_concurrent_indexing: 1` in config

**Lazy Loading**: Only enabled libraries loaded
- Disabled libraries consume no resources

**Shared Embedding**: All libraries share same Embedder instance
- Saves memory (embedding model loaded once)

### Docker Deployment Notes

- **Network mode**: `host` (required to access host's Ollama)
- **Volumes**:
  - `./data:/app/data` - Vector store, configs, exports
  - `/docs:ro` - Document source (read-only)
- **Ports**: 8000 (RAG API), 8001 (MCP SSE)
- **Health checks**: Both services have `/health` endpoints

### File Organization

```
api/
├── main.py              # FastAPI app, initializes LibraryManager
├── routes/
│   ├── libraries.py     # Library management API
│   ├── query.py         # Query API with library_id param
│   ├── agent.py         # Agent-specific endpoints
│   └── documents.py     # Document management
├── schemas/             # Pydantic models
└── middleware/          # auth, rate_limit, logging

core/
├── models.py            # Library data models
├── config.py            # YAML config loader
├── library_manager.py   # Library CRUD operations
├── parsers/             # Document parser plugins
│   ├── base.py          # BaseParser abstract class
│   ├── harmonyos.py     # HarmonyOS parser
│   └── generic.py       # Generic Markdown parser
├── exporter.py          # Data export/import
├── vector_store.py      # Multi-collection ChromaDB
├── retriever.py         # Library-aware retrieval
├── embedder.py          # Shared embedding model
├── query_expander.py    # Query expansion
├── permission_index.py  # Permission reverse index
├── answer_validator.py  # Hallucination prevention
└── generator.py         # Ollama LLM wrapper

data/
├── libraries/
│   ├── config.yaml      # Library configuration
│   └── harmonyos/       # Per-library data
├── vectorstore/         # ChromaDB multi-collection
└── exports/             # Exported data

mcp_server_sse.py        # MCP SSE server
scripts/
└── migrate_harmonyos.py # Data migration script
```

### Important Constraints

1. **Collection naming**: Libraries use `lib_{library_id}` collection names
2. **Serial indexing**: Only one library can index at a time (configurable)
3. **GPU memory**: GTX 1650 4GB - set `EMBEDDING_DEVICE=cpu` to reserve GPU for LLM
4. **Config changes**: Require service restart to take effect
5. **Data migration**: Old `harmony_docs` collection → `lib_harmonyos` (auto-migration available)
