# IDE Memory

Institutional memory system for AI-assisted development environments. A single Docker container runs PostgreSQL with pgvector, an MCP server for AI agent tool use, and a web UI for browsing — giving your team a shared, searchable knowledge base that persists across conversations and IDE sessions.

## Agent Setup

**Point your AI agent to [`docs/FOR_AGENTS.md`](docs/FOR_AGENTS.md)** — it contains step-by-step instructions your agent can follow to set everything up automatically. It will detect your IDE, pull the Docker image, install the right plugin/rules, and verify the connection with minimal input from you.

## Quick Start

```bash
docker run -d \
  --name ide-memory \
  -p 127.0.0.1:8080:8080 \
  -p 127.0.0.1:3000:3000 \
  -v memory-pgdata:/var/lib/postgresql \
  --restart unless-stopped \
  chalieai/ide-memory:latest
```

**MCP server (agents):** `http://localhost:8080/sse`
**Web UI (humans):** `http://localhost:3000`

Or use the helper script:

```bash
git clone https://github.com/chalieai/ide-memory.git
cd ide-memory
./run.sh build
./run.sh start
```

## Connecting Your IDE

### Claude Code

Quick setup (MCP connection for all projects):

```bash
claude mcp add --scope user --transport http memory http://localhost:8080/sse
```

For the full plugin with auto-triggering skills, see [`docs/SETUP.md`](docs/SETUP.md).

### Cursor (with auto-triggering rules)

```bash
cp -r docs/cursor/.cursor /path/to/your/project/.cursor
```

See [`docs/SETUP.md`](docs/SETUP.md) for global install, VS Code, Windsurf, and other IDEs.

### MCP-only (any IDE)

Add to your MCP config:

```json
{
  "mcpServers": {
    "memory": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

## MCP Tools

The server exposes four tools:

### `store_memory`

Store a decision, rule, architectural change, incident note, or any institutional knowledge.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `content` | yes | The memory content. Be descriptive — include context and reasoning. |
| `project` | yes | Project identifier (e.g. `billing-api`, `frontend-v2`). |
| `memory_type` | no | `decision` \| `rule` \| `change` \| `context` \| `incident` \| `note` (default: `note`) |
| `tags` | no | Categorization tags (e.g. `["database", "migration"]`) |
| `author` | no | Who is storing this (default: `unknown`) |
| `source` | no | `agent` \| `code_review` \| `incident` \| `meeting` \| `inferred` \| `manual` |
| `confidence` | no | `high` \| `medium` \| `low` (default: `medium`) |
| `affected_services` | no | Services impacted (e.g. `["auth-service", "billing-api"]`) |
| `affected_files` | no | File paths affected |
| `affected_modules` | no | Modules or components affected |
| `repo` | no | Repository URL or identifier |
| `file_path` | no | Primary file path relevant to this memory |
| `branch_name` | no | Branch where the change was made |
| `source_ref` | no | Reference URL (PR URL, ticket ID, commit SHA) |

### `fetch_memory`

Search and retrieve relevant memories using hybrid semantic + keyword search (Reciprocal Rank Fusion).

| Parameter | Required | Description |
|-----------|----------|-------------|
| `query` | yes | Natural language description of what you're looking for |
| `project` | no | Filter to a specific project |
| `limit` | no | Max results (default: 5, max: 20) |
| `memory_type` | no | Filter by type |
| `from_date` | no | Only memories after this date (ISO 8601) |
| `to_date` | no | Only memories before this date (ISO 8601) |
| `service` | no | Filter by affected service |
| `file` | no | Filter by affected file path (supports prefix matching) |
| `module` | no | Filter by affected module |

### `archive_memory`

Soft-delete a memory that is no longer relevant. Takes a `memory_id` (UUID).

### `update_memory`

Update an existing memory's content or metadata. Only provide fields you want to change — omitted fields remain unchanged. If content is updated, search embeddings are regenerated.

## Architecture

Everything runs in a single container:

```
┌─────────────────────────────────────────┐
│              Docker Container           │
│                                         │
│  ┌─────────────┐   ┌────────────────┐   │
│  │  MCP Server  │   │    Web UI      │   │
│  │  (FastMCP)   │   │  (Starlette)   │   │
│  │  :8080/sse   │   │  :3000         │   │
│  └──────┬───────┘   └───────┬────────┘   │
│         │                   │            │
│  ┌──────┴───────────────────┴────────┐   │
│  │    PostgreSQL 17 + pgvector       │   │
│  │    HNSW index (m=24, ef=128)      │   │
│  │    1024-dim embeddings            │   │
│  └───────────────────────────────────┘   │
│                                         │
│  Embedding: BAAI/bge-large-en-v1.5      │
│  (local CPU inference via fastembed)     │
└─────────────────────────────────────────┘
```

### Search

Hybrid search combines two retrieval strategies using Reciprocal Rank Fusion (K=60):

- **Vector search** — cosine similarity over HNSW-indexed 1024-dim embeddings from `BAAI/bge-large-en-v1.5`
- **Full-text search** — PostgreSQL `tsvector` with weighted fields (A: project/type/services, B: files/tags, C: content)

Both run concurrently via `asyncio.gather`.

### Content Processing

Long memories are split into overlapping chunks (1200 chars, 200 overlap) with sentence-aware boundaries. Each chunk is enriched with metadata context (`[project: X] [type: Y] [tags: ...]`) before embedding for better retrieval quality.

### Deduplication

Content is hashed (SHA-256, truncated to 16 chars) and checked against a unique partial index per project before storing. Duplicate submissions are rejected with a reference to the existing memory.

## Configuration

All settings are configurable via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_PORT` | `8080` | MCP server port |
| `MCP_HOST` | `0.0.0.0` | MCP server bind address |
| `WEB_PORT` | `3000` | Web UI port |
| `WEB_HOST` | `0.0.0.0` | Web UI bind address |
| `POOL_MIN` | `5` | Min DB connection pool size |
| `POOL_MAX` | `20` | Max DB connection pool size |
| `CHUNK_SIZE` | `1200` | Text chunk size in characters |
| `CHUNK_OVERLAP` | `200` | Overlap between chunks |
| `MAX_CONTENT_LENGTH` | `100000` | Max memory content length |
| `PG_SHARED_BUFFERS` | `256MB` | PostgreSQL shared_buffers |
| `PG_WORK_MEM` | `16MB` | PostgreSQL work_mem |
| `PG_EFFECTIVE_CACHE_SIZE` | `512MB` | PostgreSQL effective_cache_size |
| `PG_MAINTENANCE_WORK_MEM` | `256MB` | PostgreSQL maintenance_work_mem |
| `BACKUP_DIR` | `/app/backups` | Backup storage directory |

## Data Persistence

Mount a Docker volume to `/var/lib/postgresql` to persist data across container restarts:

```bash
-v memory-pgdata:/var/lib/postgresql
```

### Backups

Automated backups run on startup (if data exists) and hourly. Last 10 backups are retained.

Manual backup/restore via the container:

```bash
# Create a backup
docker exec ide-memory /app/scripts/backup.sh backup

# List backups
docker exec ide-memory /app/scripts/backup.sh list

# Restore from a backup
docker exec ide-memory /app/scripts/backup.sh restore /app/backups/memory_20260324_120000.dump
```

## Web UI

The web UI at `http://localhost:3000` provides:

- Full-text and semantic search across all memories
- Filter by project, type, service, file, or module
- Timeline view grouped by date
- Memory detail view with source provenance and impact scope
- Export (full or per-project)
- Dashboard with stats and recent activity

## Development

### Run Tests

Unit tests (no Docker required):

```bash
pip install pytest
pytest tests/test_chunking.py -v
```

Integration tests (requires running container):

```bash
pytest tests/test_api_live.py -v
```

### Helper Script

```bash
./run.sh build     # Build the Docker image
./run.sh start     # Start the container
./run.sh stop      # Stop and remove the container
./run.sh restart   # Stop + start
./run.sh logs      # Tail container logs
```

## Releasing

Push a tag matching `vX.X.X`:

```bash
git tag v1.0.0
git push origin v1.0.0
```

The CI workflow automatically builds multi-platform images (amd64 + arm64) and pushes to Docker Hub as `chalieai/ide-memory:vX.X.X` and `chalieai/ide-memory:latest`.

### Docker Hub Setup

Add these secrets to your GitHub repository settings:

- `DOCKERHUB_USERNAME` — your Docker Hub username
- `DOCKERHUB_TOKEN` — a Docker Hub access token

## License

Apache 2.0
