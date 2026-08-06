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

    async def get_players(self, season: str = "2025-26"):
        """Get all nba players by season by async"""
        params = {
            "LeagueID": "00",
            "Season": season,
            "IsOnlyCurrentSeason": "1"
        }

        try:
            response = await self.client.get("/commonallplayers", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error by getting players: {e}")
            return None

    async def get_games(self, season: str = "2025-26"):
        """Get all nba games by season by async"""
        params = {
            "LeagueID": "00",
            "Season": season,
            "SeasonType": "Regular Season"
        }

        try:
            response = await self.client.get("/leaguegamefinder", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error by getting matches: {e}")
            return None

    async def get_boxscore(self, game_id: str):
        """Getting boxscore by every player"""
        params = {
            "GameID": game_id,
            "StartPeriod": "0",
            "EndPeriod": "0",
            "StartRange": "0",
            "EndRange": "0",
            "RangeType": "0"
        }

        headers = {
            "Host": "stats.nba.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://stats.nba.com/",
            "x-nba-stats-origin": "stats",
            "x-nba-stats-token": "true",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache"
        }

        try:
            response = await self.client.get(
                "/boxscoretraditionalv2",
                params=params,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error by trying to get game: {game_id}: {e}")
            return None
