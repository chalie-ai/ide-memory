---
name: save-memory
description: >
  Store institutional knowledge to the shared memory system. Use this skill whenever a decision is
  made, a rule is established, an architectural change happens, an incident occurs, or important
  context is discovered during the conversation. This includes: choosing one approach over another
  (decision), establishing a pattern or constraint that should be followed going forward (rule),
  modifying architecture, schemas, or infrastructure (change), debugging production issues or
  outages (incident), and capturing project context that would help future developers (context).
  Also triggers after commits, PR merges, code reviews with significant findings, migrations,
  dependency changes, config changes, and any conversation where the user or agent says something
  worth remembering. Store proactively — don't wait to be asked. If something would be useful to
  know in a future conversation, store it now. The cost of storing too much is low; the cost of
  losing institutional knowledge is high.
---

# Store Institutional Memory

You have the ability to persist knowledge to a shared memory system that survives across all
conversations, all sessions, and all developers. **Use it proactively** — don't wait for the
user to ask you to remember something.

## When to Store

### Always store

- **Decisions** (`memory_type: "decision"`) — Any time a choice is made between alternatives. Why was option A chosen over option B? What were the tradeoffs? Example: "Chose PostgreSQL over MongoDB for the user service because we need ACID transactions for payment data and the team already has PG expertise."

- **Rules** (`memory_type: "rule"`) — Patterns, constraints, or conventions that should be followed. Example: "All database migrations must be backward-compatible — the old code must work with the new schema during rolling deploys."

- **Architectural changes** (`memory_type: "change"`) — Modifications to system design, schemas, APIs, infrastructure, or dependencies. Example: "Migrated auth-service from REST to gRPC. All inter-service calls now use protobuf. Client-facing API remains REST."

- **Incidents** (`memory_type: "incident"`) — Production issues, outages, bugs, and their root causes. Example: "Connection pool exhaustion in billing-api caused 502s for 45 minutes. Root cause: missing connection timeout on the Redis client. Fix: added 5s timeout and connection pool max of 20."

- **Context** (`memory_type: "context"`) — Background information that helps understand a project, service, or domain. Example: "The billing-api processes ~50k transactions/day. Peak hours are 9-11am UTC. The payment provider rate-limits at 100 req/s."

### Also store after

- **Commits with significant changes** — Summarize what changed and why, especially for architectural shifts
- **Code reviews** — Store significant findings, patterns discovered, or decisions made during review
- **Debugging sessions** — Document the root cause and fix, especially if it was non-obvious
- **Migration work** — Document what was migrated, gotchas encountered, and rollback procedures
- **Configuration changes** — Document what was changed, why, and what the previous values were

## How to Store

Use the `store_memory` MCP tool. Write rich, descriptive content — this will be searched semantically, so more context is better.

### Required fields

- `content` — The actual knowledge. Be descriptive. Include the **what**, **why**, and **context**. Write as if explaining to a developer who joins the team in 6 months.
- `project` — The project identifier (e.g. `billing-api`, `frontend-v2`, `infrastructure`)

### Important optional fields

Always set these when applicable:

- `memory_type` — `decision` | `rule` | `change` | `context` | `incident` | `note`
- `tags` — Categorization tags (e.g. `["database", "migration", "breaking-change"]`)
- `confidence` — `high` (verified fact) | `medium` (likely correct) | `low` (uncertain, needs validation)
- `affected_services` — Services impacted (e.g. `["auth-service", "billing-api"]`)
- `affected_files` — File paths affected (e.g. `["src/auth/middleware.ts"]`)
- `affected_modules` — Modules affected (e.g. `["authentication", "rate-limiting"]`)

### Source tracking

- `source` — How this was created: `agent` (AI conversation), `code_review`, `incident`, `meeting`, `inferred`, `manual`
- `source_ref` — Link back to the source: PR URL, ticket ID, commit SHA
- `author` — Who is storing this (your name or the user's)
- `repo` — Repository (e.g. `github.com/org/repo`)
- `file_path` — Primary file this relates to
- `branch_name` — Branch where the change was made

## Writing Good Memory Content

### Do

- Include the reasoning behind decisions, not just the outcome
- Mention alternatives that were considered and why they were rejected
- Reference specific files, services, or modules affected
- Include relevant numbers, thresholds, or configuration values
- Mention who was involved in the decision (if known)

### Don't

- Store trivial or temporary information (typo fixes, formatting changes)
- Store verbatim code — reference file paths instead
- Store speculative information as fact — use `confidence: "low"` for uncertain knowledge
- Duplicate existing memories — the system deduplicates by content hash, but try to update existing memories when information evolves rather than creating new ones

## Examples

### After an architectural decision

```
store_memory(
  content="Decided to split the monolithic user-service into separate auth-service and profile-service. Motivation: the auth endpoints have 10x the traffic of profile endpoints and need independent scaling. Auth-service will own JWT issuance and validation. Profile-service handles user preferences, avatars, and settings. Shared user ID format (UUID v4) ensures compatibility. Migration will be done over 3 sprints with a feature flag to gradually shift traffic.",
  project="user-platform",
  memory_type="decision",
  tags=["microservices", "architecture", "scaling"],
  confidence="high",
  affected_services=["auth-service", "profile-service", "user-service"],
  affected_modules=["authentication", "user-profiles"],
  source="agent",
  source_ref="https://github.com/org/user-platform/issues/234"
)
```

### After resolving an incident

```
store_memory(
  content="Production outage: billing-api returned 500s for 23 minutes during peak hours. Root cause: database connection pool (max 10) was exhausted because a new reporting query held connections for 30+ seconds. Fix: increased pool to 25, added 10s statement timeout, and moved reporting queries to a read replica. Prevention: added connection pool utilization alert at 80%.",
  project="billing-api",
  memory_type="incident",
  tags=["database", "connection-pool", "outage", "performance"],
  confidence="high",
  affected_services=["billing-api"],
  affected_files=["src/db/pool.ts", "src/reports/quarterly.ts"],
  source="incident"
)
```

### After establishing a rule

```
store_memory(
  content="All new API endpoints must include rate limiting. Default: 100 requests per minute per API key. Endpoints that modify data: 20 requests per minute. This was established after the scraping incident on 2024-03-15 where an unprotected endpoint was hit 50k times in 10 minutes.",
  project="api-gateway",
  memory_type="rule",
  tags=["rate-limiting", "security", "api-design"],
  confidence="high",
  affected_services=["api-gateway"],
  affected_modules=["rate-limiting"],
  source="incident",
  source_ref="https://github.com/org/api-gateway/issues/89"
)
```
