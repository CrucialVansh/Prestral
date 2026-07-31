"""Assert every public route is documented in OpenAPI for /docs."""

from __future__ import annotations

# Paths we expect to appear in Swagger (method, path)
EXPECTED_OPERATIONS = [
    ("get", "/health"),
    ("post", "/api/decks/upload"),
    ("get", "/api/decks"),
    ("get", "/api/decks/{deck_id}"),
    ("post", "/api/decks/{deck_id}/query"),
    ("post", "/api/decks/{deck_id}/sessions"),
    ("get", "/api/decks/{deck_id}/sessions"),
    ("get", "/api/decks/{deck_id}/sessions/{session_id}"),
    ("patch", "/api/decks/{deck_id}/sessions/{session_id}"),
    ("post", "/api/decks/{deck_id}/sessions/{session_id}/messages"),
    ("delete", "/api/decks/{deck_id}/sessions/{session_id}"),
    ("get", "/api/storage/google/auth-url"),
    ("get", "/api/storage/google/callback"),
    ("get", "/api/storage/connections"),
    ("delete", "/api/storage/connections/{connection_id}"),
    ("get", "/api/storage/files"),
    ("post", "/api/storage/import"),
]


def test_openapi_available(client) -> None:
    res = client.get("/openapi.json")
    assert res.status_code == 200
    spec = res.json()
    assert spec["info"]["title"] == "Prestral API"
    assert "decks" in {t["name"] for t in spec["tags"]}
    assert "sessions" in {t["name"] for t in spec["tags"]}
    assert "storage" in {t["name"] for t in spec["tags"]}


def test_all_endpoints_present_in_openapi(client) -> None:
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    missing = []
    for method, path in EXPECTED_OPERATIONS:
        op = paths.get(path, {}).get(method)
        if op is None:
            missing.append(f"{method.upper()} {path}")
            continue
        # Swagger usefulness: each op should have a summary and a description/docstring
        assert op.get("summary"), f"Missing summary on {method.upper()} {path}"
        assert op.get("operationId"), f"Missing operationId on {method.upper()} {path}"
    assert not missing, f"Missing from OpenAPI: {missing}"


def test_key_schemas_documented(client) -> None:
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    for name in (
        "DeckAnalysisResponse",
        "Component",
        "BBox",
        "ChatSession",
        "CreateSessionRequest",
        "SendMessageRequest",
        "QueryRequest",
        "DriveImportRequest",
        "DriveFileInfo",
    ):
        assert name in schemas, f"Schema {name} missing from OpenAPI"
        assert schemas[name].get("properties") or schemas[name].get("$ref")


def test_swagger_ui_serves(client) -> None:
    res = client.get("/docs")
    assert res.status_code == 200
    assert "swagger" in res.text.lower()
