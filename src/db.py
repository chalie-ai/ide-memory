import json
import asyncio
import asyncpg
from config import DATABASE_URL, POOL_MIN, POOL_MAX

_pool: asyncpg.Pool | None = None
_pool_lock = asyncio.Lock()

# All columns we SELECT in query functions
_COLS = """id, project, content, memory_type, author,
           repo, file_path, branch_name,
           source, source_ref,
           affected_services, affected_files, affected_modules,
           tags, metadata, confidence, last_validated_at, content_hash,
           created_at, updated_at"""

_COLS_PREFIXED = """m.id, m.project, m.content, m.memory_type, m.author,
           m.repo, m.file_path, m.branch_name,
           m.source, m.source_ref,
           m.affected_services, m.affected_files, m.affected_modules,
           m.tags, m.metadata, m.confidence, m.last_validated_at, m.content_hash,
           m.created_at, m.updated_at"""


async def _init_connection(conn):
    await conn.execute("SET hnsw.ef_search = 100")


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool
    async with _pool_lock:
        if _pool is not None:
            return _pool
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=POOL_MIN,
            max_size=POOL_MAX,
            command_timeout=30,
            init=_init_connection,
        )
        return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def _vec(embedding: list[float]) -> str:
    return "[" + ",".join(str(x) for x in embedding) + "]"


def _row_to_dict(row) -> dict:
    meta = row["metadata"]
    if isinstance(meta, str):
        meta = json.loads(meta)
    return {
        "id": str(row["id"]),
        "project": row["project"],
        "content": row["content"],
        "memory_type": row["memory_type"],
        "author": row["author"],
        "repo": row.get("repo"),
        "file_path": row.get("file_path"),
        "branch_name": row.get("branch_name"),
        "source": row.get("source", "manual"),
        "source_ref": row.get("source_ref"),
        "affected_services": list(row["affected_services"]) if row.get("affected_services") else [],
        "affected_files": list(row["affected_files"]) if row.get("affected_files") else [],
        "affected_modules": list(row["affected_modules"]) if row.get("affected_modules") else [],
        "tags": list(row["tags"]) if row["tags"] else [],
        "metadata": meta if meta else {},
        "confidence": row.get("confidence", "medium"),
        "last_validated_at": row["last_validated_at"].isoformat() if row.get("last_validated_at") else None,
        "content_hash": row.get("content_hash"),
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


def _add_scope_filters(conditions: list, params: list, idx: int,
                       project=None, memory_type=None, from_date=None, to_date=None,
                       service=None, file=None, module=None, prefix="") -> int:
    """Shared filter builder for all query functions. Returns next param index."""
    p = prefix  # "m." or ""
    if project:
        conditions.append(f"{p}project = ${idx}")
        params.append(project)
        idx += 1
    if memory_type:
        conditions.append(f"{p}memory_type = ${idx}")
        params.append(memory_type)
        idx += 1
    if from_date:
        conditions.append(f"{p}created_at >= ${idx}::timestamptz")
        params.append(from_date)
        idx += 1
    if to_date:
        conditions.append(f"{p}created_at <= ${idx}::timestamptz")
        params.append(to_date)
        idx += 1
    if service:
        conditions.append(f"${idx} = ANY({p}affected_services)")
        params.append(service)
        idx += 1
    if file:
        # Match exact file in affected_files array OR the primary file_path, with prefix support
        conditions.append(
            f"(${idx} = ANY({p}affected_files) OR {p}file_path = ${idx}"
            f" OR EXISTS (SELECT 1 FROM unnest({p}affected_files) af WHERE af LIKE ${idx} || '%')"
            f" OR {p}file_path LIKE ${idx} || '%')"
        )
        params.append(file)
        idx += 1
    if module:
        conditions.append(f"${idx} = ANY({p}affected_modules)")
        params.append(module)
        idx += 1
    return idx


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

async def store_memory(
    project: str,
    content: str,
    memory_type: str,
    author: str,
    tags: list[str],
    metadata: dict,
    chunks: list[str],
    embeddings: list[list[float]],
    repo: str | None = None,
    file_path: str | None = None,
    branch_name: str | None = None,
    source: str = "manual",
    source_ref: str | None = None,
    affected_services: list[str] | None = None,
    affected_files: list[str] | None = None,
    affected_modules: list[str] | None = None,
    confidence: str = "medium",
    content_hash: str | None = None,
) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO memories (project, content, memory_type, author, tags, metadata,
                                      repo, file_path, branch_name,
                                      source, source_ref,
                                      affected_services, affected_files, affected_modules,
                                      confidence, content_hash)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                RETURNING id, project, memory_type, author, tags, created_at
                """,
                project, content, memory_type, author, tags, json.dumps(metadata),
                repo, file_path, branch_name,
                source, source_ref,
                affected_services or [], affected_files or [], affected_modules or [],
                confidence, content_hash,
            )
            memory_id = row["id"]

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                await conn.execute(
                    """
                    INSERT INTO memory_chunks (memory_id, chunk_index, chunk_text, embedding)
                    VALUES ($1, $2, $3, $4::vector)
                    """,
                    memory_id, i, chunk, _vec(embedding),
                )

            return {
                "id": str(memory_id),
                "project": row["project"],
                "memory_type": row["memory_type"],
                "author": row["author"],
                "tags": list(row["tags"]) if row["tags"] else [],
                "created_at": row["created_at"].isoformat(),
                "chunks_count": len(chunks),
            }


# ---------------------------------------------------------------------------
# Vector similarity search
# ---------------------------------------------------------------------------

async def vector_search(
    query_embedding: list[float],
    project=None, limit=20, memory_type=None,
    from_date=None, to_date=None,
    service=None, file=None, module=None,
) -> list[dict]:
    pool = await get_pool()
    embedding_str = _vec(query_embedding)

    conditions = ["NOT m.is_archived"]
    params: list = [embedding_str]
    idx = _add_scope_filters(conditions, params, 2,
                             project, memory_type, from_date, to_date,
                             service, file, module, prefix="m.")

    where = "WHERE " + " AND ".join(conditions)
    # Fetch more to account for dedup
    fetch_limit = limit * 5
    params.append(fetch_limit)

    query = f"""
        SELECT {_COLS_PREFIXED},
               1 - (mc.embedding <=> $1::vector) AS similarity
        FROM memory_chunks mc
        JOIN memories m ON mc.memory_id = m.id
        {where}
        ORDER BY mc.embedding <=> $1::vector ASC
        LIMIT ${idx}
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    # Deduplicate: keep highest similarity per memory
    seen = {}
    for row in rows:
        mid = str(row["id"])
        sim = float(row["similarity"])
        if mid not in seen or sim > seen[mid][1]:
            seen[mid] = (row, sim)

    results = []
    for row, sim in sorted(seen.values(), key=lambda x: x[1], reverse=True)[:limit]:
        d = _row_to_dict(row)
        d["similarity"] = round(sim, 4)
        results.append(d)
    return results


# ---------------------------------------------------------------------------
# Full-text search
# ---------------------------------------------------------------------------

async def text_search(
    query: str,
    project=None, limit=20, memory_type=None,
    from_date=None, to_date=None,
    service=None, file=None, module=None,
) -> list[dict]:
    pool = await get_pool()

    conditions = [
        "search_vector @@ websearch_to_tsquery('english', $1)",
        "NOT is_archived",
    ]
    params: list = [query]
    idx = _add_scope_filters(conditions, params, 2,
                             project, memory_type, from_date, to_date,
                             service, file, module)

    where = "WHERE " + " AND ".join(conditions)
    params.append(limit)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT {_COLS},
                   ts_rank(search_vector, websearch_to_tsquery('english', $1)) AS score
            FROM memories
            {where}
            ORDER BY score DESC
            LIMIT ${idx}
            """,
            *params,
        )

    results = []
    for row in rows:
        d = _row_to_dict(row)
        d["similarity"] = round(float(row["score"]), 4)
        results.append(d)
    return results


# ---------------------------------------------------------------------------
# Hybrid search  (Reciprocal Rank Fusion)
# ---------------------------------------------------------------------------

async def hybrid_search(
    query: str,
    query_embedding: list[float],
    project=None, limit=10, memory_type=None,
    from_date=None, to_date=None,
    service=None, file=None, module=None,
) -> list[dict]:
    RRF_K = 60
    fetch_n = limit * 3

    kw = dict(project=project, memory_type=memory_type,
              from_date=from_date, to_date=to_date,
              service=service, file=file, module=module)

    vec_results, txt_results = await asyncio.gather(
        vector_search(query_embedding, limit=fetch_n, **kw),
        text_search(query, limit=fetch_n, **kw),
    )

    vec_ranks = {r["id"]: i + 1 for i, r in enumerate(vec_results)}
    txt_ranks = {r["id"]: i + 1 for i, r in enumerate(txt_results)}

    all_memories: dict[str, dict] = {}
    for r in vec_results + txt_results:
        if r["id"] not in all_memories:
            all_memories[r["id"]] = r

    scored: list[tuple[str, float]] = []
    for mid in all_memories:
        rrf = 0.0
        if mid in vec_ranks:
            rrf += 1.0 / (RRF_K + vec_ranks[mid])
        if mid in txt_ranks:
            rrf += 1.0 / (RRF_K + txt_ranks[mid])
        scored.append((mid, rrf))

    scored.sort(key=lambda x: x[1], reverse=True)

    results = []
    for mid, rrf in scored[:limit]:
        mem = all_memories[mid]
        mem["similarity"] = round(rrf, 6)
        results.append(mem)
    return results


# ---------------------------------------------------------------------------
# Listing / browsing queries
# ---------------------------------------------------------------------------

async def list_memories(
    project=None, memory_type=None, page=1, per_page=20,
    service=None, file=None, module=None,
) -> tuple[list[dict], int]:
    pool = await get_pool()

    conditions = ["NOT is_archived"]
    params: list = []
    idx = _add_scope_filters(conditions, params, 1,
                             project, memory_type, service=service,
                             file=file, module=module)

    where = "WHERE " + " AND ".join(conditions)

    async with pool.acquire() as conn:
        total = await conn.fetchval(f"SELECT COUNT(*) FROM memories {where}", *params)
        rows = await conn.fetch(
            f"""
            SELECT {_COLS}
            FROM memories {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params, per_page, (page - 1) * per_page,
        )

    return [_row_to_dict(r) for r in rows], total


async def get_memory(memory_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT {_COLS} FROM memories WHERE id = $1::uuid AND NOT is_archived",
            memory_id,
        )
    return _row_to_dict(row) if row else None


async def get_projects() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                project,
                COUNT(*) AS count,
                MAX(created_at) AS latest_at,
                COUNT(*) FILTER (WHERE memory_type = 'decision') AS decisions,
                COUNT(*) FILTER (WHERE memory_type = 'rule') AS rules,
                COUNT(*) FILTER (WHERE memory_type = 'change') AS changes,
                COUNT(*) FILTER (WHERE memory_type = 'context') AS contexts,
                COUNT(*) FILTER (WHERE memory_type = 'incident') AS incidents,
                COUNT(*) FILTER (WHERE memory_type = 'note') AS notes
            FROM memories
            WHERE NOT is_archived
            GROUP BY project
            ORDER BY MAX(created_at) DESC
        """)

    return [
        {
            "name": r["project"],
            "count": r["count"],
            "latest_at": r["latest_at"].isoformat(),
            "type_counts": {
                "decision": r["decisions"],
                "rule": r["rules"],
                "change": r["changes"],
                "context": r["contexts"],
                "incident": r["incidents"],
                "note": r["notes"],
            },
        }
        for r in rows
    ]


async def get_types() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT memory_type, COUNT(*) AS count
            FROM memories WHERE NOT is_archived
            GROUP BY memory_type ORDER BY count DESC
        """)
    return [{"name": r["memory_type"], "count": r["count"]} for r in rows]


async def get_services() -> list[dict]:
    """Get all known affected services with memory counts."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT svc, COUNT(*) AS count
            FROM memories, unnest(affected_services) AS svc
            WHERE NOT is_archived
            GROUP BY svc ORDER BY count DESC
        """)
    return [{"name": r["svc"], "count": r["count"]} for r in rows]


async def get_stats() -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                COUNT(*) AS total,
                COUNT(DISTINCT project) AS projects,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') AS this_week,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 day') AS today
            FROM memories WHERE NOT is_archived
        """)
        chunks = await conn.fetchval("SELECT COUNT(*) FROM memory_chunks")
        recent = await conn.fetch(f"""
            SELECT {_COLS}
            FROM memories WHERE NOT is_archived
            ORDER BY created_at DESC LIMIT 10
        """)

    return {
        "total_memories": row["total"],
        "total_projects": row["projects"],
        "total_chunks": chunks,
        "memories_this_week": row["this_week"],
        "memories_today": row["today"],
        "recent": [_row_to_dict(r) for r in recent],
    }


async def health_check() -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        pg_version = await conn.fetchval("SELECT version()")
        mem_count = await conn.fetchval("SELECT COUNT(*) FROM memories")
    return {"status": "healthy", "postgres": pg_version, "memories": mem_count}


async def archive_memory(memory_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE memories SET is_archived = TRUE WHERE id = $1::uuid AND NOT is_archived",
            memory_id,
        )
    return result == "UPDATE 1"


async def update_memory(memory_id: str, content: str | None = None,
                         tags: list[str] | None = None,
                         memory_type: str | None = None,
                         confidence: str | None = None,
                         affected_services: list[str] | None = None,
                         affected_files: list[str] | None = None,
                         affected_modules: list[str] | None = None) -> dict | None:
    pool = await get_pool()
    sets = []
    params = []
    idx = 1
    if content is not None:
        sets.append(f"content = ${idx}")
        params.append(content)
        idx += 1
    if tags is not None:
        sets.append(f"tags = ${idx}")
        params.append(tags)
        idx += 1
    if memory_type is not None:
        sets.append(f"memory_type = ${idx}")
        params.append(memory_type)
        idx += 1
    if confidence is not None:
        sets.append(f"confidence = ${idx}")
        params.append(confidence)
        idx += 1
    if affected_services is not None:
        sets.append(f"affected_services = ${idx}")
        params.append(affected_services)
        idx += 1
    if affected_files is not None:
        sets.append(f"affected_files = ${idx}")
        params.append(affected_files)
        idx += 1
    if affected_modules is not None:
        sets.append(f"affected_modules = ${idx}")
        params.append(affected_modules)
        idx += 1
    if not sets:
        return await get_memory(memory_id)
    params.append(memory_id)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE memories SET {', '.join(sets)} WHERE id = ${idx}::uuid AND NOT is_archived RETURNING {_COLS}",
            *params,
        )
    return _row_to_dict(row) if row else None


async def check_duplicate(project: str, content_hash: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT {_COLS} FROM memories WHERE project = $1 AND content_hash = $2 AND NOT is_archived",
            project, content_hash,
        )
    return _row_to_dict(row) if row else None


async def export_memories(project: str | None = None) -> list[dict]:
    pool = await get_pool()
    conditions = ["NOT is_archived"]
    params = []
    idx = 1
    if project:
        conditions.append(f"project = ${idx}")
        params.append(project)
        idx += 1
    where = "WHERE " + " AND ".join(conditions)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT {_COLS} FROM memories {where} ORDER BY created_at DESC",
            *params,
        )
    return [_row_to_dict(r) for r in rows]


async def pool_stats() -> dict:
    if _pool is None:
        return {"status": "not_initialized"}
    return {
        "size": _pool.get_size(),
        "free": _pool.get_idle_size(),
        "used": _pool.get_size() - _pool.get_idle_size(),
        "min": _pool.get_min_size(),
        "max": _pool.get_max_size(),
    }
