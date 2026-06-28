"""FastAPI route integration tests.

Tests the API layer contract (schemas, status codes, headers) without
needing a live Ollama or Qdrant instance. The SQLite audit DB is
redirected to a temporary file so tests never touch the project's data/.

Run:
    pytest tests/integration/ -v
    pytest tests/integration/ -m "not requires_services"   # same — CI safe

To run tests that need live services:
    pytest tests/integration/ -m requires_services
"""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """
    Start the FastAPI app with:
    - audit DB redirected to a temp file (real SQLite, not mocked)
    - BM25 corpus path pointing at a non-existent temp file (returns empty)

    Both patches must be active when TestClient enters the lifespan context
    so that init_db() writes to the temp file rather than data/audit.db.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_db   = Path(tmp) / "audit.db"
        tmp_bm25 = Path(tmp) / "bm25_corpus.json"

        with (
            patch("backend.audit.logger._DB_PATH",              new=tmp_db),
            patch("backend.config.settings.bm25_corpus_path",   new=str(tmp_bm25)),
        ):
            from backend.api.main import app
            with TestClient(app) as c:
                yield c


# ── /health ──────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_health_returns_200(client):
    with (
        patch("backend.api.routes.health.ollama") as mock_ollama,
        patch("backend.api.routes.health.QdrantClient") as mock_qdrant,
    ):
        mock_ollama.Client.return_value.list.return_value = []
        mock_qdrant.return_value.get_collections.return_value = MagicMock(collections=[])

        resp = client.get("/health")
        assert resp.status_code == 200


@pytest.mark.integration
def test_health_schema(client):
    with (
        patch("backend.api.routes.health.ollama") as mock_ollama,
        patch("backend.api.routes.health.QdrantClient") as mock_qdrant,
    ):
        mock_ollama.Client.return_value.list.return_value = []
        mock_qdrant.return_value.get_collections.return_value = MagicMock(collections=[])

        body = client.get("/health").json()
        assert "status"           in body
        assert "ollama"           in body
        assert "qdrant"           in body
        assert "bm25_corpus_size" in body


@pytest.mark.integration
def test_health_degrades_when_ollama_down(client):
    """If Ollama is unreachable, /health must still return 200 — status is 'degraded'."""
    with (
        patch("backend.api.routes.health.ollama") as mock_ollama,
        patch("backend.api.routes.health.QdrantClient") as mock_qdrant,
    ):
        mock_ollama.Client.return_value.list.side_effect = ConnectionRefusedError("offline")
        mock_qdrant.return_value.get_collections.return_value = MagicMock(collections=[])

        resp  = client.get("/health")
        body  = resp.json()
        assert resp.status_code == 200            # never 5xx — degraded, not dead
        assert body["status"]  == "degraded"
        assert "unavailable"   in body["ollama"]


# ── /query validation ────────────────────────────────────────────────────────

@pytest.mark.integration
def test_query_rejects_empty_body(client):
    resp = client.post("/query", json={})
    assert resp.status_code == 422


@pytest.mark.integration
def test_query_rejects_missing_question(client):
    resp = client.post("/query", json={"session_id": "abc"})
    assert resp.status_code == 422


@pytest.mark.integration
def test_query_stream_rejects_empty_body(client):
    resp = client.post("/query/stream", json={})
    assert resp.status_code == 422


@pytest.mark.integration
def test_query_requires_json_content_type(client):
    resp = client.post("/query", data="not json", headers={"Content-Type": "text/plain"})
    assert resp.status_code in (415, 422)


# ── /sources ─────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_sources_returns_200_on_empty_corpus(client):
    """With no BM25 corpus file, /sources returns 200 with an empty list."""
    resp = client.get("/sources")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── /audit-log ───────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_audit_log_returns_empty_on_fresh_db(client):
    resp = client.get("/audit-log")
    assert resp.status_code == 200
    body = resp.json()
    assert "entries" in body
    assert body["entries"] == []


@pytest.mark.integration
def test_audit_log_unknown_id_returns_404(client):
    resp = client.get("/audit-log/non-existent-id-000")
    assert resp.status_code == 404


# ── OpenAPI / docs ────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_openapi_docs_available(client):
    assert client.get("/docs").status_code == 200


@pytest.mark.integration
def test_openapi_schema_available(client):
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"].startswith("Sovereign RAG")
    assert "/query" in schema["paths"]
    assert "/health" in schema["paths"]
