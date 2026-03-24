"""Live integration tests against the running container.

Run with: pytest tests/test_api_live.py -v
Requires the Docker container to be running on localhost:3000.
"""
import json
import urllib.request
import urllib.error

BASE = "http://localhost:3000"


def api_get(path: str, timeout: int = 10):
    url = f"{BASE}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read()), resp.status, resp.headers


# ---------------------------------------------------------------------------
# Health & Infrastructure
# ---------------------------------------------------------------------------

def test_health_endpoint():
    data, status, _ = api_get("/health")
    assert status == 200
    assert data["status"] == "healthy"
    assert "postgres" in data
    assert "memories" in data
    assert "pool" in data
    assert data["pool"]["size"] >= 1


def test_health_has_pool_stats():
    data, _, _ = api_get("/health")
    pool = data["pool"]
    assert "size" in pool
    assert "free" in pool
    assert "used" in pool
    assert "min" in pool
    assert "max" in pool
    assert pool["max"] == 20


# ---------------------------------------------------------------------------
# Security Headers
# ---------------------------------------------------------------------------

def test_security_headers():
    _, _, headers = api_get("/api/stats")
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert "strict-origin" in headers.get("Referrer-Policy", "")
    assert "default-src" in headers.get("Content-Security-Policy", "")


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_endpoint():
    data, status, _ = api_get("/api/stats")
    assert status == 200
    assert data["total_memories"] >= 1
    assert data["total_projects"] >= 1
    assert "total_chunks" in data
    assert "recent" in data
    assert isinstance(data["recent"], list)


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

def test_projects_endpoint():
    data, status, _ = api_get("/api/projects")
    assert status == 200
    assert isinstance(data["projects"], list)
    assert len(data["projects"]) >= 1
    p = data["projects"][0]
    assert "name" in p
    assert "count" in p
    assert "type_counts" in p


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

def test_types_endpoint():
    data, status, _ = api_get("/api/types")
    assert status == 200
    assert isinstance(data["types"], list)
    valid_types = {"decision", "rule", "change", "context", "incident", "note"}
    for t in data["types"]:
        assert t["name"] in valid_types


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

def test_services_endpoint():
    data, status, _ = api_get("/api/services")
    assert status == 200
    assert isinstance(data["services"], list)
    # Services may be empty if no memories have affected_services set
    if data["services"]:
        assert "name" in data["services"][0]
        assert "count" in data["services"][0]


# ---------------------------------------------------------------------------
# Memories List
# ---------------------------------------------------------------------------

def test_memories_list():
    data, status, _ = api_get("/api/memories?per_page=5")
    assert status == 200
    assert "memories" in data
    assert "total" in data
    assert "page" in data
    assert "pages" in data
    assert len(data["memories"]) <= 5


def test_memories_list_filter_by_project():
    data, _, _ = api_get("/api/memories?project=billing-api")
    assert all(m["project"] == "billing-api" for m in data["memories"])


def test_memories_list_filter_by_service():
    data, _, _ = api_get("/api/memories?service=auth-service")
    for m in data["memories"]:
        assert (
            "auth-service" in m.get("affected_services", [])
            or "auth-service" in m.get("project", "")
        )


def test_memories_list_pagination():
    data, _, _ = api_get("/api/memories?page=1&per_page=2")
    assert data["page"] == 1
    assert len(data["memories"]) <= 2


def test_memories_list_bad_page_param():
    data, status, _ = api_get("/api/memories?page=abc")
    assert status == 200  # Falls back to default, not 500
    assert data["page"] == 1


# ---------------------------------------------------------------------------
# Memory Detail
# ---------------------------------------------------------------------------

def test_memory_detail():
    list_data, _, _ = api_get("/api/memories?per_page=1")
    if list_data["memories"]:
        mid = list_data["memories"][0]["id"]
        data, status, _ = api_get(f"/api/memories/{mid}")
        assert status == 200
        mem = data["memory"]
        assert mem["id"] == mid
        assert "content" in mem
        assert "memory_type" in mem
        assert "source" in mem
        assert "confidence" in mem
        assert "affected_services" in mem
        assert "affected_files" in mem
        assert "affected_modules" in mem
        assert "content_hash" in mem


def test_memory_detail_not_found():
    try:
        api_get("/api/memories/00000000-0000-0000-0000-000000000000")
        assert False, "Should have returned 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def test_search_empty_query():
    data, status, _ = api_get("/api/search?q=")
    assert status == 200
    assert data["memories"] == []
    assert data["count"] == 0


def test_search_returns_results():
    # First search may be slow — embedding model loads on first call
    data, status, _ = api_get("/api/search?q=database+architecture", timeout=60)
    assert status == 200
    assert isinstance(data["memories"], list)
    # Should return at least 1 result
    assert data["count"] >= 1


def test_search_with_project_filter():
    data, _, _ = api_get("/api/search?q=migration&project=billing-api", timeout=60)
    for m in data["memories"]:
        assert m["project"] == "billing-api"


def test_search_with_type_filter():
    data, _, _ = api_get("/api/search?q=security&type=incident")
    for m in data["memories"]:
        assert m["memory_type"] == "incident"


def test_search_bad_limit():
    data, status, _ = api_get("/api/search?q=test&limit=notanumber")
    assert status == 200  # Falls back to default


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

def test_timeline():
    data, status, _ = api_get("/api/timeline")
    assert status == 200
    assert "groups" in data
    assert "total" in data
    if data["groups"]:
        g = data["groups"][0]
        assert "date" in g
        assert "memories" in g


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def test_export_all():
    data, status, _ = api_get("/api/export")
    assert status == 200
    assert isinstance(data["memories"], list)
    assert data["count"] >= 1
    assert "exported_at" in data


def test_export_by_project():
    data, _, _ = api_get("/api/export?project=auth-service")
    assert all(m["project"] == "auth-service" for m in data["memories"])


# ---------------------------------------------------------------------------
# Memory Fields Completeness
# ---------------------------------------------------------------------------

def test_memory_has_all_required_fields():
    data, _, _ = api_get("/api/memories?per_page=1")
    if data["memories"]:
        m = data["memories"][0]
        required_fields = [
            "id", "project", "content", "memory_type", "author",
            "source", "tags", "metadata", "confidence",
            "affected_services", "affected_files", "affected_modules",
            "created_at", "updated_at",
        ]
        for field in required_fields:
            assert field in m, f"Missing field: {field}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
