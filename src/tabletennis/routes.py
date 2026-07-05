__all__ = ["router"]

import asyncio
import datetime as dtm
import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from pydantic import EmailStr

from src.dependencies import INH_TOKEN_AUTH
from src.inh_accounts_sdk import inh_accounts
from src.logging_ import logger

from .admin_config import TABLETENNIS_ADMIN_AUTH
from .mongo import Game, Player, Tournament

router = APIRouter(tags=["Table Tennis"], route_class=AutoDeriveResponsesAPIRoute)

K_FACTOR = 32


def isactive(last_game_date: dtm.datetime) -> bool:
    return dtm.datetime.now(dtm.UTC) - last_game_date < dtm.timedelta(days=30)


async def format_player_data(player: Player) -> dict[str, Any]:
    """Format player data with name and activity status."""
    try:
        acc = await inh_accounts.get_user(innohassle_id=player.innohassle_id)
        if acc and acc.innopolis_info:
            name = acc.innopolis_info.name
        else:
            name = player.nickname
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to fetch account for {player.innohassle_id}: {e}")
        name = player.nickname

    player_dict = player.model_dump(mode="json")

    player_dict["name"] = name
    player_dict["is_active"] = isactive(player.last_game)

    if "_id" in player_dict:
        player_dict["id"] = player_dict["_id"]
        del player_dict["_id"]

    return player_dict


@router.get("/get_player")
async def get_player(auth: INH_TOKEN_AUTH) -> dict[str, Any]:
    """
    Returns the current player's data with name from InNoHassle Accounts
    and calculated activity status.
    """
    player = await Player.find_one(Player.innohassle_id == auth.innohassle_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    return await format_player_data(player)


@router.get("/players")
async def list_players(auth: INH_TOKEN_AUTH) -> dict[str, Any]:
    """
    Returns a list of all registered players with their names from InNoHassle Accounts
    and their calculated activity status.
    """
    players = await Player.find().to_list()

    formatted_players = await asyncio.gather(*(format_player_data(p) for p in players))

    return {"total": len(formatted_players), "players": formatted_players}


@router.get("/ping")
def ping(auth: INH_TOKEN_AUTH):
    """
    To check that all is good.
    """
    return "All good."


@router.post("/reg")
async def register_player(auth: INH_TOKEN_AUTH, nick: str | None = None) -> Player:
    """To register/rename player."""
    if nick and (len(nick) < 2 or len(nick) > 20):
        raise HTTPException(status_code=400, detail="Nickname must be between 2 and 20 characters long!")

    player = await Player.find_one(Player.innohassle_id == auth.innohassle_id)
    if player:
        if nick:
            player.nickname = nick
            await player.save()

        return player

    logger.info(f"Try to make new player, id: {auth.innohassle_id}")

    account_info = await inh_accounts.get_user(innohassle_id=auth.innohassle_id)
    if nick:
        name_to_display = nick
    elif account_info:
        name_to_display = account_info.innopolis_info.name
    else:
        name_to_display = auth.email.split("@")[0]

    ancient_date = dtm.datetime(2000, 1, 1, tzinfo=dtm.UTC)
    new_player = Player(
        innohassle_id=auth.innohassle_id,
        nickname=name_to_display,
        rating=1000,
        wins=0,
        losses=0,
        last_game=ancient_date,
    )

    await new_player.insert()
    logger.info(f"New player {new_player.nickname} succefille created!")
    return new_player


@router.post("/reg_tour")
async def register_tour(
    auth: TABLETENNIS_ADMIN_AUTH, name: str, players: list[EmailStr], date: dtm.datetime | None = None
) -> Tournament:
    """
    Creates a new tournament with a list of participating players.
    """
    if len(players) < 2:
        raise HTTPException(status_code=400, detail="A tournament must have at least 2 players!")

    for email in players:
        acc = await inh_accounts.get_user(email=email)
        if not acc:
            raise HTTPException(status_code=404, detail=f"User {email} not found in InNoHassle Accounts")
        p = await Player.find_one(Player.innohassle_id == acc.id)
        if not p:
            raise HTTPException(status_code=400, detail=f"Player {email} must register via /reg first!")

    tour_id = str(uuid.uuid4())[:8]
    new_tournament = Tournament(
        id=tour_id,
        name=name,
        players=players,
        val_games=[],
        cval_games=[],
        date=dtm.datetime.now(tz=dtm.UTC) if not date else date,
    )

    await new_tournament.insert()
    logger.info(f"Tournament '{name}' ({tour_id}) successfully created by admin {auth.email}")
    return new_tournament


@router.post("/reg_game")
async def register_game(
    auth: TABLETENNIS_ADMIN_AUTH, tour_id: str, tip: Literal["val", "cval"], email1: EmailStr, email2: EmailStr
) -> dict[str, Any]:
    """
    Creates a new game in tournament with start score 0:0.
    """
    if email1 == email2:
        raise HTTPException(status_code=400, detail="A player cannot play a match against themselves!")

    tournament = await Tournament.find_one(Tournament.id == tour_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    if email1 not in tournament.players or email2 not in tournament.players:
        raise HTTPException(status_code=400, detail="One or both players are not in this tournament's player list")

    acc1 = await inh_accounts.get_user(email=email1)
    acc2 = await inh_accounts.get_user(email=email2)

    if not acc1 or not acc2:
        raise HTTPException(status_code=404, detail="One or both users not found in InNoHassle Accounts")

    p1 = await Player.find_one(Player.innohassle_id == acc1.id)
    p2 = await Player.find_one(Player.innohassle_id == acc2.id)

    if not p1 or not p2:
        raise HTTPException(status_code=404, detail="One or both players are not registered in the system (/reg)")

    game_id = str(uuid.uuid4())[:8]
    new_game = Game(
        tour_id=tour_id,
        game_id=game_id,
        player1_id=p1.innohassle_id,
        player2_id=p2.innohassle_id,
        player1_score=0,
        player2_score=0,
    )
    await new_game.insert()

    if tip == "val":
        if tournament.valGames is None:
            tournament.valGames = []
        tournament.valGames.append(new_game)
    else:
        if tournament.cvalGames is None:
            tournament.cvalGames = []
        tournament.cvalGames.append(new_game)

    await tournament.save()
    logger.info(f"Game between {p1.nickname} and {p2.nickname} registered in tournament {tour_id}")

    return {"status": "success", "message": "Game successfully registered in tournament", "game_id": str(new_game.id)}


@router.post("/game")
async def finish_game(auth: TABLETENNIS_ADMIN_AUTH, game_id: str, s1: int, s2: int, tour_id: str) -> dict[str, Any]:
    """
    Admin endpoint to record a match result using game_id and tour_id.
    Calculates Elo, updates player stats, and synchronizes scores inside the tournament.
    """
    if s1 == s2:
        raise HTTPException(status_code=400, detail="Draws are not allowed in table tennis!")

    tournament = await Tournament.find_one(Tournament.id == tour_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    target_game: Game | None = None

    for list_name in ["val_games", "cval_games"]:
        games_list = getattr(tournament, list_name)
        if games_list:
            for game in games_list:
                if game.game_id == game_id:
                    target_game = game
                    break
        if target_game:
            break

    if not target_game:
        raise HTTPException(status_code=404, detail="Game not found in this tournament")

    p1_id = target_game.player1_id
    p2_id = target_game.player2_id

    p1 = await Player.find_one(Player.innohassle_id == p1_id)
    p2 = await Player.find_one(Player.innohassle_id == p2_id)

    if not p1 or not p2:
        raise HTTPException(status_code=404, detail="One or both players from this game are not registered (/reg)")

    target_game.player1_score = s1
    target_game.player2_score = s2

    db_game = await Game.find_one(Game.game_id == game_id)
    if db_game:
        db_game.player1_score = s1
        db_game.player2_score = s2
        await db_game.save()

    r1 = p1.rating
    r2 = p2.rating

    expected_1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
    expected_2 = 1 / (1 + 10 ** ((r1 - r2) / 400))

    actual_1 = 1.0 if s1 > s2 else 0.0
    actual_2 = 1.0 if s2 > s1 else 0.0

    delta_1 = round(K_FACTOR * (actual_1 - expected_1))
    delta_2 = round(K_FACTOR * (actual_2 - expected_2))

    if delta_1 == 0:
        delta_1 = 1 if actual_1 == 1.0 else -1
    if delta_2 == 0:
        delta_2 = 1 if actual_2 == 1.0 else -1

    if p1.rating > 1500 and p2.status == "Beginner" and s1 > s2:
        delta_1, delta_2 = 0, 0
    if p2.rating > 1500 and p1.status == "Beginner" and s2 > s1:
        delta_1, delta_2 = 0, 0

    new_r1 = p1.rating + delta_1
    new_r2 = p2.rating + delta_2

    if p1.status == "Advanced" and new_r1 < 1500:
        delta_1 = 1500 - p1.rating
    if p2.status == "Advanced" and new_r2 < 1500:
        delta_2 = 1500 - p2.rating

    p1.rating += delta_1
    p2.rating += delta_2

    current_time = dtm.datetime.now(tz=dtm.UTC)
    p1.last_game = current_time
    p2.last_game = current_time

    if s1 > s2:
        p1.wins += 1
        p2.losses += 1
    else:
        p2.wins += 1
        p1.losses += 1

    if p1.rating > 1500 and p1.status != "Admin":
        p1.status = "Advanced"
    if p2.rating > 1500 and p2.status != "Admin":
        p2.status = "Advanced"

    await tournament.save()
    await p1.save()
    await p2.save()

    logger.info(
        f"Match {game_id} in tour {tour_id} saved: {p1.nickname} ({s1}) vs {p2.nickname} ({s2}). "
        f"Elo: {p1.nickname} ({'+' if delta_1 >= 0 else ''}{delta_1}), {p2.nickname} ({'+' if delta_2 >= 0 else ''}{delta_2})"
    )

    return {
        "status": "success",
        "game_id": game_id,
        "player1": {"nickname": p1.nickname, "new_rating": p1.rating, "delta": delta_1, "league": p1.status},
        "player2": {"nickname": p2.nickname, "new_rating": p2.rating, "delta": delta_2, "league": p2.status},
    }
