# Changelog

## [0.1.1] - 2026-03-24

### Changed

- Switch MCP transport from SSE (`/sse`) to streamable-http (`/mcp`). The server now calls `mcp.run(transport="streamable-http")` and the endpoint path changes accordingly.
- Update all IDE setup configs, docs, and scripts to use the new endpoint (`http://host:port/mcp`) and transport type (`http`).
- Claude Code CLI command updated from `--transport sse` to `--transport http`.
- `.mcp.json` examples now show `"type": "http"` and `"url": "http://host:port/mcp"`.
