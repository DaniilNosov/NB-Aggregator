from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import or_, select, func, desc
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


@app.post("/sync-players")
async def sync_players(db: AsyncSession = Depends(get_db)):
    """Parsing and saving all players to database"""
    client = NBADataClient()
    try:
        data = await client.get_players(season="2022-23")
        if not data:
            return {"error": "Could not get players"}

        result_sets = data.get("resultSets", [])
        players_set = next((rs for rs in result_sets if rs["name"] == "CommonAllPlayers"), None)

        if not players_set:
            return {"error": "No players found"}

        headers = players_set["headers"]
        person_id_idx = headers.index("PERSON_ID")
        name_idx = headers.index("DISPLAY_FIRST_LAST")
        team_id_idx = headers.index("TEAM_ID")

        rows = players_set["rowSet"]
        added_count = 0

        for row in rows:
            player_id = row[person_id_idx]
            full_name = row[name_idx]
            team_id = row[team_id_idx]

            valid_team_id = team_id if team_id != 0 else None

            result = await db.execute(select(Player).where(Player.id == player_id))
            existing_player = result.scalar_one_or_none()

            if not existing_player:
                name_parts = full_name.split(" ", 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else ""

                new_player = Player(
                    id=player_id,
                    first_name=first_name,
                    last_name=last_name,
                )
                db.add(new_player)
                added_count += 1

        await db.commit()
        return {"status": "success", "added_players": added_count}

    finally:
        await client.close()


@app.get("/leaders/points")
async def get_top_scorers(limit: int = 10, db: AsyncSession = Depends(get_db)):
    """Returning top scoring players"""

    # Строим SQL-запрос с JOIN и агрегацией
    query = (
        select(
            Player.first_name,
            Player.last_name,
            func.round(func.avg(PlayerMatchStat.points), 1).label("avg_pts")
        )
        .join(PlayerMatchStat, Player.id == PlayerMatchStat.player_id)
        .group_by(Player.id)
        .order_by(desc("avg_pts"))
        .limit(limit)
    )

    result = await db.execute(query)
    leaders = result.all()

    response_data = []
    for rank, row in enumerate(leaders, start=1):
        response_data.append({
            "rank": rank,
            "name": f"{row.first_name} {row.last_name}".strip(),
            "avg_points": float(row.avg_pts)
        })

    return {"status": "success", "limit": limit, "leaders": response_data}


from fastapi import HTTPException


@app.get("/players/{player_id}/stats")
async def get_player_stats(player_id: int, db: AsyncSession = Depends(get_db)):
    """Returning stats for a player"""

    query = (
        select(
            Player.first_name,
            Player.last_name,
            func.round(func.avg(PlayerMatchStat.points), 1).label("avg_pts"),
            func.round(func.avg(PlayerMatchStat.rebounds), 1).label("avg_reb"),
            func.round(func.avg(PlayerMatchStat.assists), 1).label("avg_ast"),
            func.count(PlayerMatchStat.match_id).label("games_played")
        )
        .join(PlayerMatchStat, Player.id == PlayerMatchStat.player_id, isouter=True)  # isouter=True это LEFT JOIN
        .where(Player.id == player_id)
        .group_by(Player.id)
    )

    result = await db.execute(query)
    player_data = result.first()

    if not player_data:
        raise HTTPException(status_code=404, detail="Игрок не найден")

    return {
        "status": "success",
        "player_id": player_id,
        "name": f"{player_data.first_name} {player_data.last_name}".strip(),
        "stats": {
            "games_played": player_data.games_played,
            "avg_points": float(player_data.avg_pts) if player_data.avg_pts else 0.0,
            "avg_rebounds": float(player_data.avg_reb) if player_data.avg_reb else 0.0,
            "avg_assists": float(player_data.avg_ast) if player_data.avg_ast else 0.0,
        }
    }
