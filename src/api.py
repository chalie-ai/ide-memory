import json
import logging
import os
from collections import OrderedDict
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
import uvicorn

from config import WEB_PORT, WEB_HOST
from db import (
    hybrid_search as db_search,
    list_memories as db_list,
    get_memory as db_get,
    get_projects as db_projects,
    get_types as db_types,
    get_services as db_services,
    get_stats as db_stats,
    health_check as db_health,
    export_memories as db_export,
    pool_stats as db_pool_stats,
)
from embeddings import async_generate_embedding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("web-api")

STATIC_DIR = os.getenv("STATIC_DIR", "/app/static")


# ---------------------------------------------------------------------------
# Security Headers Middleware
# ---------------------------------------------------------------------------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        return response


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

async def search(request):
    q = request.query_params.get("q", "").strip()
    if not q:
        return JSONResponse({"memories": [], "count": 0})

    project = request.query_params.get("project", "").strip() or None
    memory_type = request.query_params.get("type", "").strip() or None
    from_date = request.query_params.get("from", "").strip() or None
    to_date = request.query_params.get("to", "").strip() or None
    service = request.query_params.get("service", "").strip() or None
    file = request.query_params.get("file", "").strip() or None
    module = request.query_params.get("module", "").strip() or None
    try:
        limit = min(int(request.query_params.get("limit", "20")), 50)
    except (ValueError, TypeError):
        limit = 20

    embedding = await async_generate_embedding(q)
    results = await db_search(
        query=q,
        query_embedding=embedding,
        project=project,
        limit=limit,
        memory_type=memory_type,
        from_date=from_date,
        to_date=to_date,
        service=service,
        file=file,
        module=module,
    )
    return JSONResponse({"memories": results, "count": len(results)})


async def memories_list(request):
    project = request.query_params.get("project", "").strip() or None
    memory_type = request.query_params.get("type", "").strip() or None
    service = request.query_params.get("service", "").strip() or None
    file = request.query_params.get("file", "").strip() or None
    module = request.query_params.get("module", "").strip() or None
    try:
        page = max(int(request.query_params.get("page", "1")), 1)
    except (ValueError, TypeError):
        page = 1
    try:
        per_page = min(int(request.query_params.get("per_page", "20")), 100)
    except (ValueError, TypeError):
        per_page = 20

    memories, total = await db_list(project, memory_type, page, per_page,
                                     service=service, file=file, module=module)
    return JSONResponse({
        "memories": memories,
        "total": total,
        "page": page,
        "pages": max(1, -(-total // per_page)),
    })


async def memory_detail(request):
    mid = request.path_params["id"]
    mem = await db_get(mid)
    if not mem:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse({"memory": mem})


async def projects(request):
    return JSONResponse({"projects": await db_projects()})


async def types(request):
    return JSONResponse({"types": await db_types()})


async def services(request):
    return JSONResponse({"services": await db_services()})


async def timeline(request):
    project = request.query_params.get("project", "").strip() or None
    memory_type = request.query_params.get("type", "").strip() or None
    service = request.query_params.get("service", "").strip() or None
    file = request.query_params.get("file", "").strip() or None
    module = request.query_params.get("module", "").strip() or None
    try:
        page = max(int(request.query_params.get("page", "1")), 1)
    except (ValueError, TypeError):
        page = 1
    try:
        per_page = min(int(request.query_params.get("per_page", "50")), 200)
    except (ValueError, TypeError):
        per_page = 50

    memories, total = await db_list(project, memory_type, page, per_page,
                                     service=service, file=file, module=module)

    groups: OrderedDict[str, list] = OrderedDict()
    for m in memories:
        day = m["created_at"][:10]
        groups.setdefault(day, []).append(m)

    return JSONResponse({
        "groups": [{"date": k, "memories": v} for k, v in groups.items()],
        "total": total,
        "page": page,
        "pages": max(1, -(-total // per_page)),
    })


async def stats(request):
    return JSONResponse(await db_stats())


async def export(request):
    project = request.query_params.get("project", "").strip() or None
    memories = await db_export(project)
    return JSONResponse({
        "memories": memories,
        "count": len(memories),
        "project": project,
        "exported_at": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
    })


async def health(request):
    try:
        info = await db_health()
        pool = await db_pool_stats()
        info["pool"] = pool
        return JSONResponse(info)
    except Exception as e:
        return JSONResponse({"status": "unhealthy", "error": str(e)}, status_code=503)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

routes = [
    Route("/api/search", search),
    Route("/api/memories/{id}", memory_detail),
    Route("/api/memories", memories_list),
    Route("/api/projects", projects),
    Route("/api/types", types),
    Route("/api/services", services),
    Route("/api/timeline", timeline),
    Route("/api/stats", stats),
    Route("/api/export", export),
    Route("/health", health),
    Mount("/", app=StaticFiles(directory=STATIC_DIR, html=True)),
]

app = Starlette(
    routes=routes,
    middleware=[
        Middleware(SecurityHeadersMiddleware),
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    ],
)

if __name__ == "__main__":
    logger.info("Starting web UI on %s:%s", WEB_HOST, WEB_PORT)
    uvicorn.run(app, host=WEB_HOST, port=WEB_PORT, log_level="info")
