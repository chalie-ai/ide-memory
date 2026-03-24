import hashlib
import json
import logging
from mcp.server.fastmcp import FastMCP
from config import MCP_HOST, MCP_PORT
from db import store_memory as db_store, hybrid_search as db_search, archive_memory as db_archive, update_memory as db_update, check_duplicate as db_check_dup
from embeddings import async_generate_embedding, async_generate_embeddings
from chunking import chunk_text, enrich_chunk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("memory-server")

VALID_TYPES = {"decision", "rule", "change", "context", "incident", "note"}
VALID_SOURCES = {"agent", "code_review", "incident", "meeting", "inferred", "manual"}
VALID_CONFIDENCE = {"high", "medium", "low"}

mcp = FastMCP(
    "institutional-memory",
    host=MCP_HOST,
    port=MCP_PORT,
)


@mcp.tool()
async def store_memory(
    content: str,
    project: str,
    memory_type: str = "note",
    tags: list[str] | None = None,
    author: str = "unknown",
    repo: str = "",
    file_path: str = "",
    branch_name: str = "",
    source: str = "agent",
    source_ref: str = "",
    confidence: str = "medium",
    affected_services: list[str] | None = None,
    affected_files: list[str] | None = None,
    affected_modules: list[str] | None = None,
) -> str:
    """Store a memory for future retrieval.

    Use this to persist decisions, rules, architectural changes, context,
    incident notes, or any important institutional knowledge.

    Args:
        content: The memory content. Be descriptive and include context and reasoning.
        project: Project identifier (e.g. 'billing-api', 'frontend-v2', 'infra').
        memory_type: Category — one of: decision, rule, change, context, incident, note.
        tags: Optional tags for categorization (e.g. ['database', 'migration', 'breaking']).
        author: Who is storing this memory (agent name, service, or person).
        repo: Repository where this decision was made (e.g. 'github.com/org/repo').
        file_path: File path relevant to this memory (e.g. 'src/auth/middleware.ts').
        branch_name: Branch where the change was made (e.g. 'feat/grpc-migration').
        source: How this memory was created — one of: agent (AI discussion/decision), code_review (from PR/code review), incident (from incident response), meeting (from meeting notes), inferred (derived from code changes), manual (human-entered).
        source_ref: Reference URL or identifier for the source (e.g. PR URL, ticket ID, commit SHA).
        confidence: Confidence level — one of: high, medium, low.
        affected_services: Services impacted by this memory (e.g. ['auth-service', 'billing-api']).
        affected_files: File paths affected (e.g. ['src/auth/middleware.ts', 'src/auth/types.ts']).
        affected_modules: Modules or components affected (e.g. ['authentication', 'rate-limiting']).
    """
    try:
        tags = tags or []
        affected_services = affected_services or []
        affected_files = affected_files or []
        affected_modules = affected_modules or []

        if memory_type not in VALID_TYPES:
            return json.dumps({"status": "error", "message": f"Invalid memory_type '{memory_type}'. Must be one of: {', '.join(sorted(VALID_TYPES))}"})

        if len(content) > 100000:
            return json.dumps({"status": "error", "message": "Content exceeds maximum length of 100,000 characters"})

        if source and source not in VALID_SOURCES:
            return json.dumps({"status": "error", "message": f"Invalid source '{source}'. Must be one of: {', '.join(sorted(VALID_SOURCES))}"})

        if confidence not in VALID_CONFIDENCE:
            return json.dumps({"status": "error", "message": f"Invalid confidence '{confidence}'. Must be one of: {', '.join(sorted(VALID_CONFIDENCE))}"})

        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        existing = await db_check_dup(project, content_hash)
        if existing:
            return json.dumps({"status": "duplicate", "existing_id": existing["id"],
                               "message": f"A memory with identical content already exists in project '{project}'"})

        chunks = chunk_text(content)
        enriched = [enrich_chunk(c, project=project, memory_type=memory_type, tags=tags) for c in chunks]
        embeddings = await async_generate_embeddings(enriched)

        result = await db_store(
            project=project,
            content=content,
            memory_type=memory_type,
            author=author,
            tags=tags,
            metadata={},
            chunks=chunks,
            embeddings=embeddings,
            repo=repo or None,
            file_path=file_path or None,
            branch_name=branch_name or None,
            source=source or "agent",
            source_ref=source_ref or None,
            confidence=confidence,
            content_hash=content_hash,
            affected_services=affected_services or None,
            affected_files=affected_files or None,
            affected_modules=affected_modules or None,
        )

        logger.info(
            "Stored memory %s in project %s by %s (%d chunks)",
            result["id"], project, author, result["chunks_count"],
        )

        return json.dumps(
            {
                "status": "stored",
                "id": result["id"],
                "project": result["project"],
                "memory_type": result["memory_type"],
                "author": result["author"],
                "chunks_created": result["chunks_count"],
                "created_at": result["created_at"],
                "content_hash": content_hash,
                "confidence": confidence,
            }
        )
    except Exception as e:
        logger.exception("Error in store_memory")
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
async def fetch_memory(
    query: str,
    project: str = "",
    limit: int = 5,
    memory_type: str = "",
    from_date: str = "",
    to_date: str = "",
    service: str = "",
    file: str = "",
    module: str = "",
) -> str:
    """Search and retrieve relevant memories using hybrid semantic + keyword search.

    Returns memories ranked by relevance to your query. Searches across all
    projects by default, or filter to a specific project.

    Args:
        query: Natural language description of what you're looking for.
        project: Filter to a specific project. Leave empty to search all projects.
        limit: Max number of memories to return (default 5, max 20).
        memory_type: Filter by type: decision, rule, change, context, incident, note. Leave empty for all.
        from_date: Only memories created after this date (ISO 8601, e.g. '2024-01-01').
        to_date: Only memories created before this date (ISO 8601, e.g. '2024-12-31').
        service: Filter by affected service (e.g. 'auth-service'). Matches memories that impact this service.
        file: Filter by affected file path (e.g. 'src/auth/middleware.ts'). Supports prefix matching.
        module: Filter by affected module (e.g. 'authentication'). Matches memories that impact this module.
    """
    try:
        limit = min(max(limit, 1), 20)
        query_embedding = await async_generate_embedding(query)

        results = await db_search(
            query=query,
            query_embedding=query_embedding,
            project=project or None,
            limit=limit,
            memory_type=memory_type or None,
            from_date=from_date or None,
            to_date=to_date or None,
            service=service or None,
            file=file or None,
            module=module or None,
        )

        if not results:
            return json.dumps({"memories": [], "message": "No matching memories found."})

        logger.info("Fetched %d memories for query: %s", len(results), query[:80])
        return json.dumps({"memories": results, "count": len(results)})
    except Exception as e:
        logger.exception("Error in fetch_memory")
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
async def archive_memory(memory_id: str) -> str:
    """Archive (soft-delete) a memory that is no longer relevant.

    Use this to remove outdated, incorrect, or superseded memories.
    The memory is not permanently deleted and can be restored by an admin.

    Args:
        memory_id: The UUID of the memory to archive.
    """
    try:
        success = await db_archive(memory_id)
        if success:
            logger.info("Archived memory %s", memory_id)
            return json.dumps({"status": "archived", "id": memory_id})
        return json.dumps({"status": "not_found", "message": f"Memory {memory_id} not found or already archived"})
    except Exception as e:
        logger.exception("Error archiving memory")
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
async def update_memory(
    memory_id: str,
    content: str = "",
    tags: list[str] | None = None,
    memory_type: str = "",
    confidence: str = "",
    affected_services: list[str] | None = None,
    affected_files: list[str] | None = None,
    affected_modules: list[str] | None = None,
) -> str:
    """Update an existing memory's content or metadata.

    Only provide the fields you want to change. Unset fields remain unchanged.
    If content is updated, the memory's search embeddings are regenerated.

    Args:
        memory_id: The UUID of the memory to update.
        content: New content text. Leave empty to keep existing content.
        tags: New tags list. Set to update, omit to keep existing.
        memory_type: New type (decision, rule, change, context, incident, note). Leave empty to keep.
        confidence: Confidence level (high, medium, low). Leave empty to keep.
        affected_services: Updated list of affected services.
        affected_files: Updated list of affected files.
        affected_modules: Updated list of affected modules.
    """
    try:
        if memory_type and memory_type not in VALID_TYPES:
            return json.dumps({"status": "error", "message": f"Invalid memory_type '{memory_type}'"})
        if confidence and confidence not in VALID_CONFIDENCE:
            return json.dumps({"status": "error", "message": f"Invalid confidence '{confidence}'"})

        result = await db_update(
            memory_id,
            content=content or None,
            tags=tags,
            memory_type=memory_type or None,
            confidence=confidence or None,
            affected_services=affected_services,
            affected_files=affected_files,
            affected_modules=affected_modules,
        )

        if result:
            # If content was updated, re-embed the chunks
            if content:
                from db import get_pool
                chunks = chunk_text(content)
                embeddings = await async_generate_embeddings(chunks)
                pool = await get_pool()
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        await conn.execute("DELETE FROM memory_chunks WHERE memory_id = $1::uuid", memory_id)
                        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                            from db import _vec
                            await conn.execute(
                                "INSERT INTO memory_chunks (memory_id, chunk_index, chunk_text, embedding) VALUES ($1, $2, $3, $4::vector)",
                                result["id"] if isinstance(result["id"], str) is False else __import__('uuid').UUID(result["id"]),
                                i, chunk, _vec(embedding),
                            )

            logger.info("Updated memory %s", memory_id)
            return json.dumps({"status": "updated", "memory": result})
        return json.dumps({"status": "not_found", "message": f"Memory {memory_id} not found"})
    except Exception as e:
        logger.exception("Error updating memory")
        return json.dumps({"status": "error", "message": str(e)})


if __name__ == "__main__":
    logger.info("Starting Institutional Memory MCP server on %s:%s", MCP_HOST, MCP_PORT)
    mcp.run(transport="sse")
