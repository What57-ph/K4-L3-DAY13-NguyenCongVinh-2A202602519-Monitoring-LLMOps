from __future__ import annotations

import asyncio
import httpx

from app.main import app


def test_correlation_id_middleware_generated() -> None:
    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/health")

    response = asyncio.run(send_request())
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    correlation_id = response.headers["x-request-id"]
    assert correlation_id.startswith("req-")
    assert len(correlation_id) == 12  # "req-" + 8 hex chars = 12
    assert "x-response-time-ms" in response.headers


def test_correlation_id_middleware_provided() -> None:
    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/health", headers={"x-request-id": "custom-req-123"})

    response = asyncio.run(send_request())
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "custom-req-123"
    assert "x-response-time-ms" in response.headers
