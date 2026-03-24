"""Seed enriched memories with source provenance and impact scope."""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from db import store_memory, get_pool, close_pool
from embeddings import generate_embeddings
from chunking import chunk_text

MEMORIES = [
    {
        "project": "billing-api",
        "content": "Decided to migrate from Stripe's Charges API to PaymentIntents API to support SCA (Strong Customer Authentication) requirements in the EU. This is a breaking change for all checkout flows. The migration must be completed before the regulatory deadline. All webhook handlers need updating to handle the new event types.",
        "memory_type": "decision",
        "author": "payments-agent",
        "tags": ["payments", "stripe", "sca", "eu-compliance", "breaking-change"],
        "repo": "github.com/acme/billing-api",
        "file_path": "src/payments/stripe_client.py",
        "branch_name": "feat/payment-intents-migration",
        "source": "code_review",
        "source_ref": "https://github.com/acme/billing-api/pull/342",
        "affected_services": ["billing-api", "checkout-frontend", "webhook-processor"],
        "affected_files": ["src/payments/stripe_client.py", "src/payments/webhooks.py", "src/checkout/payment_flow.py"],
        "affected_modules": ["payments", "checkout", "webhooks"],
    },
    {
        "project": "auth-service",
        "content": "Implemented JWT token rotation with sliding window refresh. Access tokens expire in 15 minutes, refresh tokens in 7 days. On each refresh, old refresh token is invalidated immediately (rotation). Added Redis-backed token blacklist for immediate revocation support. This replaces the previous long-lived session token approach flagged by security audit.",
        "memory_type": "change",
        "author": "security-agent",
        "tags": ["jwt", "security", "token-rotation", "redis"],
        "repo": "github.com/acme/auth-service",
        "file_path": "src/auth/token_manager.ts",
        "branch_name": "feat/jwt-rotation",
        "source": "agent",
        "source_ref": "SEC-2024-087",
        "affected_services": ["auth-service", "api-gateway", "user-dashboard"],
        "affected_files": ["src/auth/token_manager.ts", "src/auth/middleware.ts", "src/redis/token_store.ts"],
        "affected_modules": ["authentication", "authorization", "session-management"],
    },
    {
        "project": "data-pipeline",
        "content": "Rule: All ETL jobs must implement idempotent writes using MERGE/UPSERT patterns. Never use INSERT without ON CONFLICT handling. This was established after the March 2024 incident where a failed-and-retried Spark job duplicated 2.3M records in the analytics warehouse, causing incorrect revenue reports for 3 days.",
        "memory_type": "rule",
        "author": "data-eng-lead",
        "tags": ["etl", "idempotency", "data-quality", "spark"],
        "repo": "github.com/acme/data-pipeline",
        "file_path": "docs/engineering-standards.md",
        "branch_name": "main",
        "source": "incident",
        "source_ref": "INC-2024-0312",
        "affected_services": ["data-pipeline", "analytics-warehouse", "reporting-service"],
        "affected_files": ["jobs/revenue_etl.py", "jobs/user_events_etl.py", "lib/db_writer.py"],
        "affected_modules": ["etl-framework", "data-ingestion", "reporting"],
    },
    {
        "project": "frontend-v2",
        "content": "Migrating from Redux to Zustand for state management. Redux boilerplate is slowing down feature development — a simple feature addition requires changes in 5+ files (action types, action creators, reducers, selectors, connect). Zustand reduces this to a single store file. Migration will be incremental: new features use Zustand, existing Redux stores migrated during planned refactors.",
        "memory_type": "decision",
        "author": "frontend-architect",
        "tags": ["react", "state-management", "zustand", "redux", "dx"],
        "repo": "github.com/acme/frontend-v2",
        "file_path": "src/stores/README.md",
        "branch_name": "chore/zustand-migration",
        "source": "meeting",
        "source_ref": "https://notion.so/acme/frontend-arch-meeting-2024-03-15",
        "affected_services": ["frontend-v2", "component-library"],
        "affected_files": ["src/stores/cart.ts", "src/stores/user.ts", "src/stores/notifications.ts"],
        "affected_modules": ["state-management", "cart", "user-profile", "notifications"],
    },
    {
        "project": "api-gateway",
        "content": "Implemented adaptive rate limiting using token bucket algorithm with Redis backend. Limits are per-API-key with configurable burst (default: 100 req/s sustained, 200 req/s burst). Added automatic degradation: when Redis is unavailable, falls back to in-memory rate limiting per instance (less accurate but prevents total failure). Dashboard alerts configured for >80% limit utilization.",
        "memory_type": "change",
        "author": "platform-agent",
        "tags": ["rate-limiting", "redis", "resilience", "api-gateway"],
        "repo": "github.com/acme/api-gateway",
        "file_path": "src/middleware/rate_limiter.go",
        "branch_name": "feat/adaptive-rate-limits",
        "source": "agent",
        "source_ref": "https://github.com/acme/api-gateway/pull/178",
        "affected_services": ["api-gateway", "auth-service", "billing-api"],
        "affected_files": ["src/middleware/rate_limiter.go", "src/middleware/rate_limiter_test.go", "config/rate_limits.yaml"],
        "affected_modules": ["rate-limiting", "middleware", "monitoring"],
    },
    {
        "project": "infra",
        "content": "Production Kubernetes cluster upgraded from 1.27 to 1.29. Key breaking changes addressed: 1) Removed flowcontrol.apiserver.k8s.io/v1beta2 - migrated all FlowSchema objects. 2) Pod Security Standards now enforced (not just warned). 3) HPA v2 autoscaling metrics API changes. All staging environments validated for 2 weeks before production rollout.",
        "memory_type": "change",
        "author": "infra-agent",
        "tags": ["kubernetes", "upgrade", "breaking-change", "infrastructure"],
        "repo": "github.com/acme/infra",
        "file_path": "terraform/k8s/cluster.tf",
        "branch_name": "chore/k8s-1.29-upgrade",
        "source": "agent",
        "source_ref": "OPS-2024-K8S-UPGRADE",
        "affected_services": ["api-gateway", "billing-api", "auth-service", "data-pipeline", "frontend-v2"],
        "affected_files": ["terraform/k8s/cluster.tf", "k8s/base/pod-security.yaml", "k8s/base/hpa.yaml"],
        "affected_modules": ["infrastructure", "kubernetes", "deployment"],
    },
    {
        "project": "auth-service",
        "content": "Incident: Authentication service returned 503 for 23 minutes during peak traffic. Root cause: connection pool exhaustion in PostgreSQL adapter. Pool was configured for max 10 connections but peak auth load requires 40+. Fixed by increasing pool max to 50, adding connection timeout of 5s (was infinite), and implementing circuit breaker pattern to fail fast when pool is saturated.",
        "memory_type": "incident",
        "author": "oncall-agent",
        "tags": ["outage", "connection-pool", "postgresql", "circuit-breaker"],
        "repo": "github.com/acme/auth-service",
        "file_path": "src/db/pool.ts",
        "branch_name": "fix/connection-pool-exhaustion",
        "source": "incident",
        "source_ref": "INC-2024-0298",
        "affected_services": ["auth-service", "api-gateway", "user-dashboard", "mobile-api"],
        "affected_files": ["src/db/pool.ts", "src/db/config.ts", "src/middleware/circuit_breaker.ts"],
        "affected_modules": ["database", "connection-management", "resilience"],
    },
    {
        "project": "billing-api",
        "content": "Context: The billing system uses a two-phase commit pattern for subscription changes. Phase 1: Create pending change record in our DB. Phase 2: Apply change in Stripe. Phase 3: Confirm in our DB. If Phase 2 fails, a reconciliation job (runs every 5 min) detects orphaned pending records and rolls them back. This ensures we never have billing state drift between our system and Stripe.",
        "memory_type": "context",
        "author": "billing-agent",
        "tags": ["billing", "stripe", "consistency", "two-phase-commit"],
        "repo": "github.com/acme/billing-api",
        "file_path": "src/subscriptions/change_handler.py",
        "branch_name": "main",
        "source": "inferred",
        "source_ref": "",
        "affected_services": ["billing-api", "subscription-manager"],
        "affected_files": ["src/subscriptions/change_handler.py", "src/subscriptions/reconciler.py", "src/jobs/billing_reconciliation.py"],
        "affected_modules": ["subscriptions", "billing-reconciliation", "payments"],
    },
]


async def main():
    pool = await get_pool()
    for i, mem in enumerate(MEMORIES):
        content = mem["content"]
        chunks = chunk_text(content)
        embeddings = generate_embeddings(chunks)

        result = await store_memory(
            project=mem["project"],
            content=content,
            memory_type=mem["memory_type"],
            author=mem["author"],
            tags=mem["tags"],
            metadata={},
            chunks=chunks,
            embeddings=embeddings,
            repo=mem.get("repo"),
            file_path=mem.get("file_path"),
            branch_name=mem.get("branch_name"),
            source=mem.get("source", "manual"),
            source_ref=mem.get("source_ref") or None,
            affected_services=mem.get("affected_services"),
            affected_files=mem.get("affected_files"),
            affected_modules=mem.get("affected_modules"),
        )
        print(f"  [{i+1}/{len(MEMORIES)}] Stored: {result['id']} ({mem['project']}/{mem['memory_type']})")

    await close_pool()
    print(f"\nDone. Seeded {len(MEMORIES)} enriched memories.")


if __name__ == "__main__":
    asyncio.run(main())
