from fastapi import FastAPI
from src.core.config import settings
from src.services.nba_client import NBADataClient

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Агрегатор баскетбольной статистики для портфолио",
    version="1.0.0"
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "db_url_loaded": settings.DATABASE_URL is not None}



@app.get("/test-nba-teams")
async def test_nba_teams():
    client = NBADataClient()
    try:
        data = await client.get_teams()
        return data
    finally:
        await client.close()
