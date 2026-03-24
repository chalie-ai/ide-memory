---
name: fetch-memory
description: >
  Fetch institutional memory before doing work. Use this skill CONSTANTLY — before writing code,
  investigating bugs, making architectural decisions, reviewing PRs, starting any task, answering
  questions about the codebase, or doing research. Even if you think you know the answer, check
  memory first — previous decisions, incidents, rules, and context are stored there and ignoring
  them leads to repeated mistakes and contradictory decisions. Triggers on: code changes, debugging,
  refactoring, architecture discussions, "why was this done", "what do we know about", incident
  investigation, onboarding questions, planning, design reviews, dependency changes, migration work,
  and any task where historical context would help. When in doubt, fetch. The cost of a redundant
  fetch is near zero; the cost of missing critical context is high.
---

# Fetch Institutional Memory

You have access to a shared knowledge base that persists across all conversations and all developers.
It contains decisions, rules, architectural context, incident notes, and lessons learned. **Use it.**

## When to Fetch

Fetch memory at the **start of every task**, not just when the user asks. Specifically:

- **Before writing or modifying code** — check if there are decisions, rules, or past incidents related to the files, modules, or services you're touching
- **Before making architectural decisions** — someone may have already evaluated the options and documented why one was chosen
- **When investigating bugs** — check for past incidents involving the same service, file, or module
- **When answering "why" questions** — "why do we use X", "why is this code like this", "what happened with Y"
- **Before refactoring** — check for rules or decisions that constrain how things should be structured
- **When starting a new feature** — fetch context about the project, related services, and any relevant decisions
- **During code review** — check if changes align with existing decisions and rules
- **When planning migrations or upgrades** — look for past migration notes and lessons learned

## How to Fetch

Use the `fetch_memory` MCP tool. Write your query in natural language — the system uses hybrid semantic + keyword search, so be descriptive.

### Good queries

Effective queries describe what you're looking for with enough context:

- `"authentication middleware decisions and rules for the billing-api project"`
- `"incidents involving the payment processing service in the last 6 months"`
- `"why did we choose PostgreSQL over MongoDB for the user service"`
- `"database migration rules and lessons learned"`
- `"rate limiting architecture and configuration decisions"`

### Use filters to narrow results

- `project` — filter to a specific project (e.g. `billing-api`, `frontend-v2`)
- `memory_type` — filter by type: `decision`, `rule`, `change`, `context`, `incident`, `note`
- `service` — filter by affected service (e.g. `auth-service`)
- `file` — filter by affected file path (supports prefix matching)
- `module` — filter by affected module (e.g. `authentication`)
- `from_date` / `to_date` — time range (ISO 8601)

### Multiple fetches are fine

Don't try to cram everything into one query. If you're working on auth middleware for the billing API, make two calls:

1. `fetch_memory(query="authentication middleware", project="billing-api")`
2. `fetch_memory(query="auth-service incidents and rules", service="auth-service")`

## How to Use Results

- **Decisions**: Respect them. If a decision was made, don't silently contradict it. If you think it should change, surface it to the user.
- **Rules**: Follow them. Rules exist because someone learned the hard way.
- **Incidents**: Learn from them. If a past incident is relevant, mention it and explain how your approach avoids the same problem.
- **Context**: Use it to inform your work. Don't make the user re-explain things that are already documented.
- **Changes**: Be aware of recent architectural changes that might affect your work.

If fetch returns no results, that's fine — proceed normally. But always check first.
