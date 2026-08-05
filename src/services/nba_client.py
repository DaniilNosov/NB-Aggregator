import httpx
import logging

logger = logging.getLogger(__name__)


class NBADataClient:
    def __init__(self):
        self.base_url = "https://stats.nba.com/stats"

        self.headers = {
            "Host": "stats.nba.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.nba.com/",
            "Origin": "https://www.nba.com",
            "Connection": "keep-alive",
        }

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=15.0
        )

    async def get_teams(self):
        """Get all nba teams by async"""
        params = {"LeagueID": "00"}

        try:
            response = await self.client.get("/commonteamyears", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error: {e}")
            return {"error": str(e)}

    async def close(self):
        """Close the client connection"""
        await self.client.aclose()
