# tests/test_auth.py
"""Tests du middleware ApiKeyMiddleware.

Utilise `unauthed_client` (sans header) pour tester les cas 401,
et `client` (avec header valide) pour confirmer les cas 200.
"""


async def test_missing_api_key_returns_401(unauthed_client):
    resp = await unauthed_client.get("/api/families")
    assert resp.status_code == 401


async def test_wrong_api_key_returns_401(unauthed_client):
    resp = await unauthed_client.get(
        "/api/families", headers={"X-API-Key": "completely-wrong-key"}
    )
    assert resp.status_code == 401


async def test_valid_api_key_returns_200(unauthed_client):
    resp = await unauthed_client.get(
        "/api/families", headers={"X-API-Key": "test-orkestra-api-key"}
    )
    assert resp.status_code == 200


async def test_health_endpoint_is_public(unauthed_client):
    """GET /api/health ne doit pas exiger de clé API."""
    resp = await unauthed_client.get("/api/health")
    assert resp.status_code == 200


async def test_options_preflight_bypasses_auth(unauthed_client):
    """Les requêtes OPTIONS (CORS preflight) ne doivent pas être bloquées."""
    resp = await unauthed_client.options("/api/families")
    assert resp.status_code != 401


async def test_error_body_contains_detail(unauthed_client):
    """La réponse 401 doit inclure un champ 'detail'."""
    resp = await unauthed_client.get("/api/families")
    body = resp.json()
    assert "detail" in body


async def test_valid_client_fixture_passes_auth(client):
    """La fixture client standard (avec header) doit accéder aux routes protégées."""
    resp = await client.get("/api/families")
    assert resp.status_code == 200
