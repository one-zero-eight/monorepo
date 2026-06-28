__all__ = ["router"]

from fastapi import APIRouter, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.dependencies import INH_TOKEN_AUTH

from . import tabletennis_repo
from .schemas import Game, Player

router = APIRouter(tags=["Table Tennis"], route_class=AutoDeriveResponsesAPIRoute)


@router.get("/players/")
def list_players(auth: INH_TOKEN_AUTH) -> list[Player]:
    return tabletennis_repo.get_all_players()


@router.get("/players/{player_id}")
def get_player(auth: INH_TOKEN_AUTH, player_id: str) -> Player:
    player = tabletennis_repo.get_player(player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


@router.get("/games/")
def list_games(auth: INH_TOKEN_AUTH) -> list[Game]:
    return tabletennis_repo.get_all_games()


@router.get("/games/{game_id}")
def get_game(auth: INH_TOKEN_AUTH, game_id: str) -> Game:
    game = tabletennis_repo.get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return game
