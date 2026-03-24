# IDE Memory — Setup Guide

## 1. Start the server

```bash
docker run -d \
  --name ide-memory \
  -p 127.0.0.1:8080:8080 \
  -p 127.0.0.1:3000:3000 \
  -v memory-pgdata:/var/lib/postgresql \
  --restart unless-stopped \
  chalieai/ide-memory:latest
```

Verify it's running:

```bash
curl http://localhost:3000/health
```

## 2. Connect your IDE

### Option A: Claude Code (MCP + auto-triggering skills)

**Quick setup** — add the MCP server globally (applies to all projects):

```bash
claude mcp add --scope user --transport http memory http://localhost:8080/sse
```

This gives you the MCP tools (`store_memory`, `fetch_memory`, etc.) in all Claude Code sessions. For auto-triggering behavior, drop `docs/CLAUDE.md` into your project roots.

**Full plugin setup** — includes auto-triggering skills so Claude fetches and stores memory without being asked:

1. Register the marketplace in `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "chalie-ai": {
      "source": {
        "source": "github",
        "repo": "chalie-ai/ide-memory",
        "path": "docs/plugin"
      }
    }
  }
}
```

2. Install the plugin (run inside Claude Code):

```
/plugin install ide-memory@chalie-ai
```

3. Enable the plugin in `~/.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "ide-memory@chalie-ai": true
  }
}
```

> **Note:** Simply copying files to `~/.claude/plugins/` does **not** register the plugin. Claude Code discovers plugins through its marketplace system — the `extraKnownMarketplaces` + `/plugin install` flow is required.

### Option B: Cursor (rules with auto-triggering)

Copy the `.cursor` directory into your project root:

```bash
cp -r docs/cursor/.cursor /path/to/your/project/.cursor
```

Or install globally (applies to all projects):

```bash
cp docs/cursor/.cursor/mcp.json ~/.cursor/mcp.json
mkdir -p ~/.cursor/rules
cp docs/cursor/.cursor/rules/*.mdc ~/.cursor/rules/
```

This gives you:
- MCP connection via `.cursor/mcp.json`
- Two `alwaysApply: true` rules that instruct the LLM to fetch and store memory automatically

### Option C: MCP-only (any IDE)

Add to your MCP configuration:

**Claude Code** (global, applies to all projects):

```bash
claude mcp add --scope user --transport http memory http://localhost:8080/sse
```

Or for a single project, create `.mcp.json` in the project root:

```json
{
  "memory": {
    "type": "sse",
    "url": "http://localhost:8080/sse"
  }
}
```

**Cursor** (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "memory": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

**VS Code Copilot** (`.vscode/mcp.json`):

```json
{
  "servers": {
    "memory": {
      "type": "sse",
      "url": "http://localhost:8080/sse"
    }
  }
}
```

**Windsurf** (`.windsurfrules` or MCP settings):

```json
{
  "mcpServers": {
    "memory": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

This gives you the MCP tools but **not** auto-triggering. The LLM has access to the tools but won't automatically use them unless prompted.

## 3. Make the LLM use memory automatically

### With the plugin/rules (Options A & B)

The Claude Code plugin includes skills, and the Cursor rules use `alwaysApply: true` — both instruct the LLM to:
- **Fetch memory** before starting tasks, investigating bugs, making decisions, reviewing code
- **Store memory** after decisions, architectural changes, incidents, commits with significant changes

No additional setup needed.

### With MCP-only (Option C)

Drop the `docs/CLAUDE.md` template into your project root:

```bash
cp docs/CLAUDE.md /path/to/your/project/CLAUDE.md
```

Edit the file to replace `<this-project>` with your project name. Claude Code reads `CLAUDE.md` at the start of every session and will follow the instructions to fetch and store memory.

For Cursor, copy the rules instead:

```bash
cp docs/cursor/.cursor/rules/*.mdc /path/to/your/project/.cursor/rules/
```

For other IDEs, add equivalent instructions to your system prompt or rules file (`.windsurfrules`, etc.).

## 4. Verify it works

Open your IDE and start a conversation. With the plugin installed, Claude should automatically call `fetch_memory` early in the conversation. You can also test manually:

> "What decisions have been stored about this project?"

Or explicitly:

> "Store a test memory: We decided to use PostgreSQL for the user service because we need ACID transactions."

Then check the web UI at `http://localhost:3000` to see it appear.

## Configuration

All settings are configurable via environment variables passed to `docker run`:

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_PORT` | `8080` | MCP server port |
| `WEB_PORT` | `3000` | Web UI port |
| `POOL_MIN` | `5` | Min DB connection pool size |
| `POOL_MAX` | `20` | Max DB connection pool size |
| `CHUNK_SIZE` | `1200` | Text chunk size in characters |
| `CHUNK_OVERLAP` | `200` | Overlap between chunks |
| `PG_SHARED_BUFFERS` | `256MB` | PostgreSQL shared_buffers |
| `PG_WORK_MEM` | `16MB` | PostgreSQL work_mem |

## Backups

Automated backups run on startup and hourly inside the container. Manual backup/restore:

```bash
# Create backup
docker exec ide-memory /app/scripts/backup.sh backup

# List backups
docker exec ide-memory /app/scripts/backup.sh list

# Restore
docker exec ide-memory /app/scripts/backup.sh restore /app/backups/<file>.dump
```

## Troubleshooting

**Container won't start**: Check if ports 8080/3000 are already in use: `lsof -i :8080`

**MCP connection fails**: Ensure the container is healthy: `docker inspect --format='{{.State.Health.Status}}' ide-memory`

**Search is slow on first query**: The embedding model loads on first use (~10-30s). Subsequent queries are fast.

**Skills not triggering (Claude Code)**: The plugin must be installed via the marketplace system, not by copying files. Run `/plugin install ide-memory@chalie-ai` inside Claude Code after registering the marketplace in `settings.json`. See Option A above.

**MCP tools not available (Claude Code)**: Verify with `claude mcp list` — the `memory` server should appear. If not, run `claude mcp add --scope user --transport http memory http://localhost:8080/sse`.
