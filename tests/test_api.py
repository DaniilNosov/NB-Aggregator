import pytest
from httpx import AsyncClient, ASGITransport

from src.main import app

pytestmark = pytest.mark.asyncio


async def test_health_check():
    """
    Check that the /health endpoint responds with status 200
    and the correct JSON structure.
    """
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_get_teams_endpoint():
    """
    Test for checking the teams endpoint.
    Verifies that the API returns a successful status and the correct NBA API JSON structure.
    """
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/test-nba-teams")

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, dict)

    assert "resultSets" in data

    assert len(data["resultSets"]) > 0
