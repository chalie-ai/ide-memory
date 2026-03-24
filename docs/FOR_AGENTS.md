# IDE Memory — Automated Setup Guide

You are an AI agent helping a user set up IDE Memory — an institutional knowledge base for development teams. Follow this guide step by step. Ask the user only when you need input; do as much as possible autonomously.

## Step 1: Server Setup

Ask the user:

> **Do you want to run IDE Memory locally, or connect to a hosted instance?**
>
> 1. **Local** — I'll set up a Docker container on your machine
> 2. **Hosted** — I'll connect to an existing server you or your team already runs

### Option 1: Local Setup

**Prerequisites check** — verify Docker is available:

```bash
docker --version
```

If Docker is not installed, tell the user they need Docker Desktop or Docker Engine and stop here.

**Check for existing instance** — don't create duplicates:

```bash
docker ps -a --filter name=ide-memory --format "{{.Names}} {{.Status}}"
```

If a container named `ide-memory` already exists and is running, skip to Step 2 — the server is already set up. If it exists but is stopped, start it:

```bash
docker start ide-memory
```

**Pull and start the container:**

```bash
docker run -d \
  --name ide-memory \
  -p 127.0.0.1:8080:8080 \
  -p 127.0.0.1:3000:3000 \
  -v memory-pgdata:/var/lib/postgresql \
  --restart unless-stopped \
  chalieai/ide-memory:latest
```

If port 8080 or 3000 is already in use, ask the user which ports to use instead and set them via environment variables:

```bash
docker run -d \
  --name ide-memory \
  -p 127.0.0.1:<USER_MCP_PORT>:8080 \
  -p 127.0.0.1:<USER_WEB_PORT>:3000 \
  -v memory-pgdata:/var/lib/postgresql \
  --restart unless-stopped \
  chalieai/ide-memory:latest
```

**Wait for it to be healthy** (may take 15-30 seconds on first run as PostgreSQL initializes and the embedding model loads):

```bash
docker inspect --format='{{.State.Health.Status}}' ide-memory
```

Keep checking until it reports `healthy`. Then verify:

```bash
curl -s http://localhost:8080/sse | head -2
```

You should see `event: endpoint` — this confirms the MCP server is accepting connections.

Set these values for use in Step 2:

- `MCP_URL` = `http://localhost:8080/sse`
- `WEB_URL` = `http://localhost:3000`

### Option 2: Hosted Setup

Ask the user:

> **What is the URL of your IDE Memory MCP server?** (e.g. `http://memory.internal:8080/sse`)

Verify connectivity:

```bash
curl -s <USER_PROVIDED_URL> | head -2
```

If you see `event: endpoint`, the connection works. Set:

- `MCP_URL` = the URL the user provided
- `WEB_URL` = ask the user if they also have a web UI URL (optional)

If the connection fails, help the user troubleshoot (firewall, VPN, wrong URL, server not running).

---

## Step 2: IDE Detection and Configuration

Detect which IDE the user is running. Check in this order:

```bash
# Check for Claude Code
which claude 2>/dev/null && echo "CLAUDE_CODE"

# Check for Cursor
ls -d ~/.cursor 2>/dev/null && echo "CURSOR"

# Check for VS Code
which code 2>/dev/null && echo "VSCODE"

# Check for Windsurf
ls -d ~/.windsurf 2>/dev/null && echo "WINDSURF"
```

Also check process list for running IDEs:

```bash
ps aux | grep -iE "cursor|claude|code|windsurf" | grep -v grep | head -5
```

If you can't determine the IDE, ask the user:

> **Which IDE are you using?**
>
> 1. Claude Code (terminal)
> 2. Cursor
> 3. VS Code (with Copilot)
> 4. Windsurf
> 5. Other

Then follow the appropriate setup below.

---

### IDE: Claude Code

There are two setup levels. **Quick setup** gives you the MCP tools; **Full plugin** adds auto-triggering skills.

#### Quick Setup (MCP only — recommended starting point)

Add the MCP server globally so it's available in all Claude Code sessions:

```bash
claude mcp add --scope user --transport sse memory <MCP_URL>
```

For example, with a local instance:

```bash
claude mcp add --scope user --transport sse memory http://localhost:8080/sse
```

**Verify it works:**

```bash
claude mcp list
```

The `memory` server should appear in the output.

**Add auto-triggering behavior** — copy the `CLAUDE.md` template into the user's project roots:

```bash
cp <REPO_PATH>/docs/CLAUDE.md /path/to/project/CLAUDE.md
```

Edit the file to replace `<this-project>` with the actual project name. Claude Code reads `CLAUDE.md` at the start of every session and will follow the instructions to fetch and store memory automatically.

#### Full Plugin (MCP + auto-triggering skills)

> **Important:** Simply copying files to `~/.claude/plugins/` does NOT register a plugin. Claude Code discovers plugins through its marketplace system. You must use the `extraKnownMarketplaces` + `/plugin install` flow.

**Step 1 — Register the marketplace.** Read the user's `~/.claude/settings.json` and add the `extraKnownMarketplaces` entry (merge with existing content, don't overwrite):

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

**Step 2 — Install the plugin.** Tell the user to run this inside Claude Code:

```
/plugin install ide-memory@chalie-ai
```

Or from the CLI:

```bash
claude plugin install ide-memory@chalie-ai --scope user
```

**Step 3 — Update MCP URL** (if using a non-default URL). After plugin installation, the MCP URL in the plugin defaults to `http://localhost:8080/sse`. If the user is connecting to a hosted instance, they need to update the MCP URL. Check where the plugin was installed:

```bash
cat ~/.claude/plugins/installed_plugins.json
```

Find the `installPath` for `ide-memory@chalie-ai` and edit the `.mcp.json` inside it:

```json
{
  "memory": {
    "type": "sse",
    "url": "<MCP_URL>"
  }
}
```

**What the user gets:**
- MCP connection to the memory server
- `fetch-memory` skill — auto-triggers before tasks, research, debugging, code review
- `save-memory` skill — auto-triggers after decisions, architectural changes, incidents, commits

Tell the user:

> IDE Memory is set up. Claude will now automatically fetch context before starting work and store important decisions after completing tasks. You don't need to ask it to — it happens automatically.
>
> Web UI is available at <WEB_URL> to browse and search memories.

---

### IDE: Cursor

Install Cursor rules with auto-triggering and MCP configuration.

**Decide scope** — ask the user:

> **Do you want IDE Memory enabled for all Cursor projects, or just the current one?**
>
> 1. **Global** — all projects
> 2. **This project only**

**Global install:**

```bash
# MCP config
cp <REPO_PATH>/docs/cursor/.cursor/mcp.json ~/.cursor/mcp.json

# Rules
mkdir -p ~/.cursor/rules
cp <REPO_PATH>/docs/cursor/.cursor/rules/*.mdc ~/.cursor/rules/
```

If `~/.cursor/mcp.json` already exists, **do not overwrite it**. Instead, read the existing file and merge the `memory` server entry into the existing `mcpServers` object.

**Project-level install:**

```bash
mkdir -p .cursor/rules
cp <REPO_PATH>/docs/cursor/.cursor/mcp.json .cursor/mcp.json
cp <REPO_PATH>/docs/cursor/.cursor/rules/*.mdc .cursor/rules/
```

Same merge rule for existing `mcp.json` files.

**If the user is using a non-default MCP URL**, update `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "memory": {
      "url": "<MCP_URL>"
    }
  }
}
```

**What the user gets:**
- MCP connection to the memory server
- `fetch-memory.mdc` rule (`alwaysApply: true`) — loads every conversation, instructs LLM to fetch context
- `save-memory.mdc` rule (`alwaysApply: true`) — loads every conversation, instructs LLM to store decisions

Tell the user:

> IDE Memory is set up. The Cursor rules will instruct the AI to automatically fetch context before work and store important decisions. Restart Cursor or open a new chat for the rules to take effect.
>
> Web UI is available at <WEB_URL> to browse and search memories.

---

### IDE: VS Code (Copilot)

VS Code doesn't have a rules/skills system like Claude Code or Cursor. Set up MCP only.

**Create MCP config:**

```bash
mkdir -p .vscode
```

Write `.vscode/mcp.json`:

```json
{
  "servers": {
    "memory": {
      "type": "sse",
      "url": "<MCP_URL>"
    }
  }
}
```

If `.vscode/mcp.json` already exists, merge the `memory` entry.

**Add a CLAUDE.md to the project root** for agents that read it:

```bash
cp <REPO_PATH>/docs/CLAUDE.md ./CLAUDE.md
```

Edit the `CLAUDE.md` to replace `<this-project>` with the actual project name.

Tell the user:

> IDE Memory MCP tools are now available in VS Code. The AI will have access to `store_memory` and `fetch_memory` tools. I've also added a CLAUDE.md with instructions — agents that read it will know to use memory automatically.
>
> Web UI is available at <WEB_URL>.

---

### IDE: Windsurf

**Create MCP config in Windsurf settings** (global):

The user needs to add the memory MCP server in Windsurf's MCP settings. The config is:

```json
{
  "mcpServers": {
    "memory": {
      "url": "<MCP_URL>"
    }
  }
}
```

**Add rules to the project** — create or append to `.windsurfrules` in the project root:

```markdown
# Institutional Memory

This project uses a shared institutional memory system via MCP. Use it constantly.

Before starting any task, fetch relevant context:
- Use the `fetch_memory` tool with a natural language query describing what you're about to work on
- Check for existing decisions, rules, incidents, and context before writing code

After completing significant work, store what you learned:
- Decisions → store_memory(memory_type="decision")
- Rules → store_memory(memory_type="rule")
- Architecture changes → store_memory(memory_type="change")
- Incidents → store_memory(memory_type="incident")
- Context → store_memory(memory_type="context")

Always include the project name, affected services/files/modules, and confidence level.
Include the WHY, not just the what.
```

Tell the user:

> IDE Memory is set up for Windsurf. The MCP tools are available and the rules file instructs the AI to use memory automatically.
>
> Web UI is available at <WEB_URL>.

---

### IDE: Other

For any other IDE that supports MCP, set up the MCP connection with the appropriate config format for that IDE, then add a project-level instructions file (CLAUDE.md, .cursorrules, or whatever the IDE reads) with the content from `docs/CLAUDE.md`.

---

## Step 3: Verification

Run a quick test to make sure everything works. In the user's IDE, start a new conversation and say:

> Store a test memory: We decided to use IDE Memory for institutional knowledge because it persists context across conversations and developers.

Then verify:

> Fetch any memories about IDE Memory.

If both work, the setup is complete.

If the MCP tools are not available, check:
1. The container/server is running and healthy
2. The MCP config points to the correct URL
3. The IDE was restarted after config changes (Cursor and VS Code require this)

---

## Quick Reference

| IDE | MCP Config | Auto-trigger Mechanism | Source Files |
|-----|-----------|----------------------|--------------|
| Claude Code | `claude mcp add --scope user` | Plugin skills (SKILL.md) or CLAUDE.md | `docs/plugin/`, `docs/CLAUDE.md` |
| Cursor | `.cursor/mcp.json` | Rules (`.mdc`, `alwaysApply: true`) | `docs/cursor/` |
| VS Code | `.vscode/mcp.json` | CLAUDE.md in project root | `docs/CLAUDE.md` |
| Windsurf | MCP settings | `.windsurfrules` | `docs/CLAUDE.md` |

## Docker Image

- **Image**: `chalieai/ide-memory:latest`
- **MCP port**: `8080` (SSE transport)
- **Web UI port**: `3000`
- **Data volume**: `/var/lib/postgresql`
- **Health check**: `curl http://localhost:3000/health`

## MCP Tools Available

| Tool | Purpose |
|------|---------|
| `store_memory` | Store decisions, rules, changes, incidents, context |
| `fetch_memory` | Search memories with hybrid semantic + keyword search |
| `archive_memory` | Soft-delete outdated memories |
| `update_memory` | Update existing memory content or metadata |
