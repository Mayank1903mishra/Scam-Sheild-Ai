import pytest


@pytest.mark.asyncio
async def test_health_endpoint(async_client):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert data["mode"] in ["rules", "ml", "demo"]


@pytest.mark.asyncio
async def test_root_endpoint(async_client):
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "ScamShield AI API"


@pytest.mark.asyncio
async def test_rate_limit_headers(async_client):
    response = await async_client.get("/api/v1/health")
    assert "X-Request-ID" in response.headers