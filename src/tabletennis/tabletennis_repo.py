from pathlib import Path

import yaml

from .schemas import Game, Player

data_path = Path(__file__).resolve().parent / "data.yaml"


def load_data(path: Path) -> tuple[list[Player], list[Game]]:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    players = [Player.model_validate(row) for row in raw.get("players", [])]
    games = [Game.model_validate(row) for row in raw.get("games", [])]
    return players, games


_players, _games = load_data(data_path)


def get_all_players() -> list[Player]:
    return _players


def get_player(player_id: str) -> Player | None:
    return next((p for p in _players if p.id == player_id), None)


def get_all_games() -> list[Game]:
    return _games


def get_game(game_id: str) -> Game | None:
    return next((g for g in _games if g.id == game_id), None)
