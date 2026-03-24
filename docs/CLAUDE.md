# Institutional Memory

This project uses a shared institutional memory system. **Use it constantly.**

## Before starting any task

Fetch relevant context from memory:

```
fetch_memory(query="<describe what you're about to work on>", project="<this-project>")
```

Check for existing decisions, rules, incidents, and context before writing code, making architectural choices, or investigating bugs. Don't assume you know the full history — check first.

## After completing significant work

Store what you learned:

- **Decisions made** → `store_memory(memory_type="decision", ...)`
- **Rules established** → `store_memory(memory_type="rule", ...)`
- **Architecture changed** → `store_memory(memory_type="change", ...)`
- **Incidents resolved** → `store_memory(memory_type="incident", ...)`
- **Important context** → `store_memory(memory_type="context", ...)`

Include the **why**, not just the **what**. Future developers (and future AI agents) will thank you.

## Memory MCP server

- **Endpoint**: `http://localhost:8080/mcp`
- **Web UI**: `http://localhost:3000`
- **Tools**: `store_memory`, `fetch_memory`, `archive_memory`, `update_memory`
