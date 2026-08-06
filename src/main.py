from datetime import datetime

from fastapi import FastAPI, Depends
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, aliased
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.core.config import settings
from src.db.database import get_db
from src.models.team import Team
from src.models.player import Player
from src.models.match import Match
from src.schemas.match import MatchSchema
from src.models.statistic import PlayerMatchStat
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


@app.post("/sync-teams")
async def sync_teams(db: AsyncSession = Depends(get_db)):
    """Parsing nba teams and saving them to database"""
    client = NBADataClient()
    try:
        data = await client.get_teams()

        headers = data["resultSets"][0]["headers"]
        team_id_idx = headers.index("TEAM_ID")
        abbr_idx = headers.index("ABBREVIATION")

        rows = data["resultSets"][0]["rowSet"]
        added_count = 0

        for row in rows:
            team_id = row[team_id_idx]
            abbreviation = row[abbr_idx]

            if not abbreviation:
                continue

            result = await db.execute(select(Team).where(Team.id == team_id))
            existing_team = result.scalar_one_or_none()

            if not existing_team:
                new_team = Team(
                    id=team_id,
                    name=abbreviation,
                    abbreviation=abbreviation
                )
                db.add(new_team)
                added_count += 1

        await db.commit()

        return {"status": "success", "added_teams": added_count}

    finally:
        await client.close()


@app.post("/sync-players")
async def sync_players(season: str = "2025-26", db: AsyncSession = Depends(get_db)):
    """Parsing players and saving them to database"""
    client = NBADataClient()
    try:
        data = await client.get_players(season)
        if not data:
            return {"error": "No players found"}

        headers = data["resultSets"][0]["headers"]
        person_id_idx = headers.index("PERSON_ID")
        name_idx = headers.index("DISPLAY_FIRST_LAST")

        rows = data["resultSets"][0]["rowSet"]
        added_count = 0

        for row in rows:
            player_id = row[person_id_idx]
            full_name = row[name_idx]

            name_parts = full_name.split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            # Проверяем, есть ли игрок в базе
            result = await db.execute(select(Player).where(Player.id == player_id))
            existing_player = result.scalar_one_or_none()

            if not existing_player:
                new_player = Player(
                    id=player_id,
                    first_name=first_name,
                    last_name=last_name,
                    position=None
                )
                db.add(new_player)
                added_count += 1

        await db.commit()

        return {"status": "success", "added_players": added_count, "season": season}

    finally:
        await client.close()


@app.post("/sync-matches")
async def sync_matches(season: str = "2025-26", db: AsyncSession = Depends(get_db)):
    """Parsing matches and saving them to database"""
    client = NBADataClient()
    try:
        data = await client.get_games(season)
        if not data:
            return {"error": "Cannot getting matches"}

        headers = data["resultSets"][0]["headers"]
        game_id_idx = headers.index("GAME_ID")
        team_id_idx = headers.index("TEAM_ID")
        matchup_idx = headers.index("MATCHUP")
        date_idx = headers.index("GAME_DATE")

        rows = data["resultSets"][0]["rowSet"]
        added_count = 0

        for row in rows:
            matchup = row[matchup_idx]

            if " vs. " not in matchup:
                continue

            game_id = int(row[game_id_idx])
            home_team_id = row[team_id_idx]

            away_team_abbr = matchup.split(" vs. ")[1]

            result = await db.execute(select(Team).where(Team.abbreviation == away_team_abbr))
            away_team = result.scalar_one_or_none()

            if not away_team:
                continue

            game_date = datetime.strptime(row[date_idx], "%Y-%m-%d").date()

            match_result = await db.execute(select(Match).where(Match.id == game_id))
            existing_match = match_result.scalar_one_or_none()

            if not existing_match:
                new_match = Match(
                    id=game_id,
                    date=game_date,
                    home_team_id=home_team_id,
                    away_team_id=away_team.id
                )
                db.add(new_match)
                added_count += 1

        await db.commit()
        return {"status": "success", "added_matches": added_count}

    finally:
        await client.close()


@app.get("/matches", response_model=list[MatchSchema])
async def get_matches(
        team: str = None,
        limit: int = 20,
        db: AsyncSession = Depends(get_db)
):
    """Getting all matches with fixed n+1"""

    query = select(Match).options(
        joinedload(Match.home_team),
        joinedload(Match.away_team)
    ).order_by(Match.date.desc())

    if team:
        HomeTeam = aliased(Team)
        AwayTeam = aliased(Team)

        query = query.join(HomeTeam, Match.home_team_id == HomeTeam.id) \
            .join(AwayTeam, Match.away_team_id == AwayTeam.id) \
            .where(
            or_(HomeTeam.abbreviation == team, AwayTeam.abbreviation == team)
        )

    query = query.limit(limit)

    result = await db.execute(query)
    matches = result.unique().scalars().all()

    return matches


@app.post("/sync-match-stats/{game_id}")
async def sync_match_stats(
        game_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Parsing individual match stats and saving them to database"""
    client = NBADataClient()
    try:
        api_game_id = str(game_id).zfill(10)

        data = await client.get_boxscore(api_game_id)

        print("\n--- DEBUG API ---")
        if data and "resultSets" in data:
            for rs in data["resultSets"]:
                print(f"Block: {rs['name']}, lines: {len(rs.get('rowSet', []))}")
        print("-----------------\n")


        if not data:
            return {"error": "Could not get boxscore"}

        result_sets = data.get("resultSets", [])
        player_stats_set = next((rs for rs in result_sets if rs["name"] == "PlayerStats"), None)

        if not player_stats_set:
            return {"error": "Нет данных по игрокам для этого матча"}

        headers = player_stats_set["headers"]
        player_id_idx = headers.index("PLAYER_ID")
        team_id_idx = headers.index("TEAM_ID")
        pts_idx = headers.index("PTS")
        reb_idx = headers.index("REB")
        ast_idx = headers.index("AST")

        rows = player_stats_set["rowSet"]
        added_count = 0

        for row in rows:
            player_id = row[player_id_idx]
            team_id = row[team_id_idx]

            pts = row[pts_idx] if row[pts_idx] is not None else 0
            reb = row[reb_idx] if row[reb_idx] is not None else 0
            ast = row[ast_idx] if row[ast_idx] is not None else 0

            result = await db.execute(
                select(PlayerMatchStat).where(
                    PlayerMatchStat.player_id == player_id,
                    PlayerMatchStat.match_id == game_id
                )
            )
            existing_stat = result.scalar_one_or_none()

            if not existing_stat:
                new_stat = PlayerMatchStat(
                    player_id=player_id,
                    match_id=game_id,
                    team_id=team_id,
                    points=pts,
                    rebounds=reb,
                    assists=ast
                )
                db.add(new_stat)
                added_count += 1

        await db.commit()
        return {"status": "success", "added_stats": added_count, "game_id": game_id}

    finally:
        await client.close()
