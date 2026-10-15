__all__ = ["router"]

import asyncio
import datetime as dtm
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from pydantic import EmailStr
from pymongo.asynchronous.client_session import AsyncClientSession

from src.dependencies import INH_TOKEN_AUTH
from src.inh_accounts_sdk import inh_accounts
from src.logging_ import logger

from .admin_config import TABLETENNIS_ADMIN_AUTH, is_tabletennis_admin, tabletennis_admin_ids
from .mongo import Game, Player, Tournament

router = APIRouter(tags=["Table Tennis"], route_class=AutoDeriveResponsesAPIRoute)


def isactive(last_game_date: dtm.datetime) -> bool:
    return dtm.datetime.now(dtm.UTC) - last_game_date < dtm.timedelta(days=30)


ADVANCED_RATING = 350
"A beginner reaching this rating becomes Advanced; games never take an Advanced player below it."


def _game_floor_rating(player: Player, new_rating: int) -> int:
    """
    The rating a game result may leave: never negative, and an Advanced player does not drop
    below ADVANCED_RATING (or below the current rating, if an admin set it lower by hand).
    """
    floor = min(player.rating, ADVANCED_RATING) if player.status == "Advanced" else 0
    return max(floor, new_rating)


def _promote_if_crossed(player: Player, old_rating: int) -> bool:
    """Makes the player Advanced once the rating climbs from below ADVANCED_RATING to it or above."""
    if player.status != "Advanced" and old_rating < ADVANCED_RATING <= player.rating:
        player.status = "Advanced"
        logger.info(f"{player.nickname} promoted to Advanced ({old_rating} -> {player.rating})")
        return True
    return False


def _get_k_factor(avg_rating: float) -> float:
    if avg_rating < 250:
        return 0.2
    elif avg_rating < 350:
        return 0.25
    elif avg_rating < 450:
        return 0.3
    elif avg_rating < 550:
        return 0.35
    else:
        return 0.4


def _get_d_factor(set_diff: int) -> float:
    if set_diff == 1:
        return 0.8
    elif set_diff == 2:
        return 1.0
    else:
        return 1.2


async def _get_tournament_avg_rating(tournament: Tournament) -> float:
    player_ids = tournament.players or []
    if not player_ids:
        return 300
    players = await Player.find({"innohassle_id": {"$in": player_ids}}).to_list()
    ratings = [p.rating for p in players]
    return sum(ratings) / len(ratings) if ratings else 300


def _get_player_kd(player: Player, is_winner: bool, avg_rating: float, set_diff: int) -> tuple[float, float]:
    """
    A beginner (manually flagged via /set-status) always gets D=1, with k=1 on a win
    and k=0.5 on a loss. A non-beginner always uses the tournament/set-margin tables,
    regardless of the opponent's status.
    """
    if player.status == "Beginner":
        return (1.0, 1.0) if is_winner else (0.5, 1.0)
    return _get_k_factor(avg_rating), _get_d_factor(set_diff)


async def _apply_rttf_delta(
    winner: Player, loser: Player, s_winner: int, s_loser: int, tournament: Tournament
) -> tuple[int, int]:
    set_diff = abs(s_winner - s_loser)
    diff = winner.rating - loser.rating

    if diff >= 100:
        return 0, 0

    base = (100 - diff) / 10

    avg_rating = await _get_tournament_avg_rating(tournament)
    k_w, d_w = _get_player_kd(winner, is_winner=True, avg_rating=avg_rating, set_diff=set_diff)
    k_l, d_l = _get_player_kd(loser, is_winner=False, avg_rating=avg_rating, set_diff=set_diff)

    delta_w = round(base * k_w * d_w)
    delta_l = -round(base * k_l * d_l)

    if delta_w == 0:
        delta_w = 1
    if delta_l == 0:
        delta_l = -1

    return delta_w, delta_l


async def _apply_tournament_bonuses(tournament: Tournament) -> None:
    """
    Bonuses for the final places 1-3 (qual_top). They are granted only once the standings
    contain every participant, i.e. the tournament is fully played. change-qual-top may be
    called more than once for the same tournament, so bonuses are granted at most once.
    """
    players = tournament.players or []
    if tournament.bonus_applied or not tournament.qual_top or len(players) < 16:
        return

    if set(tournament.qual_top.values()) != set(players):
        return

    top_places = sorted(tournament.qual_top.items())
    prize_players = [p_id for _, p_id in top_places[:3]]
    if len(prize_players) < 3:
        return

    # claim the bonus atomically so two concurrent calls can't both grant it
    claim = await Tournament.get_pymongo_collection().update_one(
        {"tour_id": tournament.tour_id, "bonus_applied": {"$ne": True}}, {"$set": {"bonus_applied": True}}
    )
    if claim.modified_count == 0:
        return
    tournament.bonus_applied = True

    all_players = await Player.find({"innohassle_id": {"$in": tournament.players}}).to_list()
    players_by_id = {p.innohassle_id: p for p in all_players}
    sorted_by_rating = sorted(all_players, key=lambda p: p.rating, reverse=True)
    top12_avg = sum(p.rating for p in sorted_by_rating[:12]) / min(12, len(sorted_by_rating))

    bonus_pct = {
        1: {(0, 100): 0.025, (100, 151): 0.02, (151, 201): 0.01},
        2: {(0, 100): 0.015, (100, 151): 0.01, (151, 201): 0.005},
        3: {(0, 100): 0.01, (100, 151): 0.005, (151, 201): 0.0},
    }

    place_counts: dict[int, int] = {}
    for place, p_id in top_places:
        if place <= 3:
            place_counts[place] = place_counts.get(place, 0) + 1

    for place, p_id in top_places:
        if place > 3 or p_id not in players_by_id:
            continue
        player = players_by_id[p_id]
        diff = player.rating - top12_avg
        if diff > 200:
            continue

        if diff < 100:
            pct = bonus_pct[place][(0, 100)]
        elif diff < 151:
            pct = bonus_pct[place][(100, 151)]
        else:
            pct = bonus_pct[place][(151, 201)]

        if pct > 0:
            bonus = round(player.rating * pct / place_counts.get(place, 1))
            if bonus > 0:
                old_rating = player.rating
                player.rating += bonus
                _promote_if_crossed(player, old_rating)
                await player.save()
                logger.info(f"Bonus +{bonus} for {player.nickname} (place {place}, tournament {tournament.tour_id})")


async def resolve_player(player_id: str | None = None, email: str | None = None) -> Player | None:
    """
    Resolve a registered Player either by innohassle_id or by email.

    - If player_id is given, look up the Player directly in the local DB (no network call,
      works fully offline / without InNoHassle Accounts - used for testing).
    - Else if email is given, resolve it to an innohassle_id via InNoHassle Accounts first,
      then look up the Player in the local DB.
    - If both are None, or the identifier doesn't resolve to a registered player, returns None.

    player_id takes priority if both are somehow provided.
    """
    if player_id:
        return await Player.find_one(Player.innohassle_id == player_id)

    if email:
        try:
            acc = await inh_accounts.get_user(email=email)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to resolve player by email {email}: {e}")
            return None

        if not acc:
            return None

        return await Player.find_one(Player.innohassle_id == acc.id)

    return None


async def _resolve_players(
    player_ids: list[str], emails: list[str], resolved: list[str], already_in: set[str]
) -> list[dict[str, str]]:
    """
    Appends the innohassle_ids of the found players to `resolved` (without duplicates) and returns
    the identifiers that failed. `code` is "not_found" or "already_in_tournament".
    """
    failed: list[dict[str, str]] = []
    identifiers = [(p_id, False) for p_id in player_ids] + [(email, True) for email in emails]
    for identifier, is_email in identifiers:
        player = await (resolve_player(email=identifier) if is_email else resolve_player(player_id=identifier))
        if not player:
            reason = (
                "User not found in InNoHassle Accounts or not registered in table tennis"
                if is_email
                else "Player with this ID is not registered in table tennis"
            )
            failed.append({"identifier": identifier, "code": "not_found", "reason": reason})
        elif player.innohassle_id in already_in:
            failed.append(
                {"identifier": identifier, "code": "already_in_tournament", "reason": "Already in this tournament"}
            )
        elif player.innohassle_id not in resolved:
            resolved.append(player.innohassle_id)
    return failed


async def format_player_data(player: Player, admin_ids: frozenset[str] | None = None) -> dict[str, Any]:
    """Format player data with name from InNoHassle Accounts (fallback to local nickname) and activity status."""

    player_dict = player.model_dump(mode="json")

    player_dict["is_active"] = isactive(player.last_game)
    if admin_ids is None:
        admin_ids = await tabletennis_admin_ids()
    player_dict["is_admin"] = player.innohassle_id in admin_ids

    if "_id" in player_dict:
        player_dict["id"] = player_dict["_id"]
        del player_dict["_id"]

    return player_dict


async def format_top(top: dict[int, str] | None) -> list[dict[str, Any]]:
    """
    Resolves a {place: innohassle_id} mapping into a sorted list of place/player info,
    similar in spirit to get_games_by_id's player_summary - unregistered/missing players
    are reported instead of silently dropped.
    """
    if not top:
        return []

    player_ids = list(top.values())
    players = await Player.find({"innohassle_id": {"$in": player_ids}}).to_list()
    players_by_id = {p.innohassle_id: p for p in players}

    result: list[dict[str, Any]] = []
    for place in sorted(top.keys()):
        p_id = top[place]
        player = players_by_id.get(p_id)
        result.append(
            {
                "place": place,
                "innohassle_id": p_id,
                "nickname": player.nickname if player else None,
                "rating": player.rating if player else None,
                "registered": player is not None,
            }
        )

    return result


def _validate_top(tournament: Tournament, top: dict[int, str]) -> None:
    """
    Shared validation for change_val_top / change_qual_top.
    Raises HTTPException(400) on the first violated rule.
    """
    invalid_places = [place for place in top if place < 1]
    if invalid_places:
        raise HTTPException(
            status_code=400, detail=f"Places must be positive integers (1 = first place), got: {invalid_places}"
        )

    tour_players = set(tournament.players or [])
    unknown_players = [p_id for p_id in top.values() if p_id not in tour_players]
    if unknown_players:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"These players are not participants of tournament {tournament.tour_id}",
                "unknown": unknown_players,
            },
        )

    seen: set[str] = set()
    duplicates: set[str] = set()
    for p_id in top.values():
        if p_id in seen:
            duplicates.add(p_id)
        seen.add(p_id)
    if duplicates:
        raise HTTPException(
            status_code=400, detail=f"A player cannot occupy more than one place at once: {sorted(duplicates)}"
        )


GAME_FIELDS = ("val_games", "cval_games")


async def _set_tour_fields(tournament: Tournament, **fields: Any) -> None:
    """
    Atomic $set of selected tournament fields. A full `tournament.save()` would replace the whole
    document and silently drop games that another admin registered in the meantime.
    """
    encoded: dict[str, Any] = {}
    for name, value in fields.items():
        setattr(tournament, name, value)
        encoded[name] = {str(k): v for k, v in value.items()} if name in ("val_top", "qual_top") else value
    await Tournament.get_pymongo_collection().update_one({"tour_id": tournament.tour_id}, {"$set": encoded})


def _find_tour_game(tournament: Tournament, game_id: str) -> tuple[str, Game] | None:
    for field in GAME_FIELDS:
        for game in getattr(tournament, field) or []:
            if game.game_id == game_id:
                return field, game
    return None


def _embedded_game(game: Game) -> dict[str, Any]:
    return game.model_dump(exclude={"id", "revision_id"}, exclude_none=True)


MAX_SCORE = 4
"Sets won by one player in a match (best of 7 at most). Matches the score steppers on the frontend (ScoreSheet)."


def _validate_score(s1: int, s2: int) -> None:
    if s1 < 0 or s2 < 0:
        raise HTTPException(status_code=400, detail="Scores cannot be negative")
    if s1 > MAX_SCORE or s2 > MAX_SCORE:
        raise HTTPException(status_code=400, detail=f"Scores cannot be greater than {MAX_SCORE}")
    if s1 == s2:
        raise HTTPException(status_code=400, detail="Draws are not allowed in table tennis!")


async def _in_transaction[T](callback: Callable[[AsyncClientSession], Awaitable[T]]) -> T:
    """
    Runs all writes of the callback atomically: either every write is saved or none.
    The callback may be retried on a transient conflict, so it must read what it changes itself.
    """
    client = Tournament.get_pymongo_collection().database.client
    async with client.start_session() as session:
        return await session.with_transaction(callback)


def _apply_result_to_players(
    p1: Player, p2: Player, s1: int, s2: int, delta_1: int, delta_2: int
) -> tuple[int, int, bool, bool]:
    """
    Applies a game result. Returns the rating changes actually applied (after the rating floors)
    and whether each player was promoted to Advanced by this game - both are stored in the game,
    so a score correction can roll the result back exactly.
    """
    applied: list[int] = []
    promoted: list[bool] = []
    for player, delta in ((p1, delta_1), (p2, delta_2)):
        old_rating = player.rating
        player.rating = _game_floor_rating(player, old_rating + delta)
        applied.append(player.rating - old_rating)
        promoted.append(_promote_if_crossed(player, old_rating))
    winner, loser = (p1, p2) if s1 > s2 else (p2, p1)
    winner.wins += 1
    loser.losses += 1
    return applied[0], applied[1], promoted[0], promoted[1]


def _undo_result_of_players(p1: Player, p2: Player, s1: int, s2: int, game: Game) -> None:
    for player, delta, promoted in (
        (p1, game.player1_delta or 0, game.player1_promoted),
        (p2, game.player2_delta or 0, game.player2_promoted),
    ):
        player.rating = max(0, player.rating - delta)
        if promoted:
            player.status = "Beginner"
    winner, loser = (p1, p2) if s1 > s2 else (p2, p1)
    winner.wins = max(0, winner.wins - 1)
    loser.losses = max(0, loser.losses - 1)


def _tour_stage_data(tour: Tournament) -> dict[str, Any]:
    return {
        "groups": tour.groups or {},
        "groups_locked": tour.groups_locked,
        "qual_seeding": tour.qual_seeding or [],
    }


def _find_player_group(tournament: Tournament, player_id: str) -> str | None:
    for name, members in (tournament.groups or {}).items():
        if player_id in members:
            return name
    return None


def _validate_groups(tournament: Tournament, groups: dict[str, list[str]]) -> None:
    empty_names = [name for name in groups if not name.strip()]
    if empty_names:
        raise HTTPException(status_code=400, detail="Group names must not be empty")

    tour_players = set(tournament.players or [])
    unknown_players = [p_id for members in groups.values() for p_id in members if p_id not in tour_players]
    if unknown_players:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"These players are not participants of tournament {tournament.tour_id}",
                "unknown": unknown_players,
            },
        )

    seen: set[str] = set()
    duplicates: set[str] = set()
    for members in groups.values():
        for p_id in members:
            if p_id in seen:
                duplicates.add(p_id)
            seen.add(p_id)
    if duplicates:
        raise HTTPException(status_code=400, detail=f"A player cannot be in more than one group: {sorted(duplicates)}")


async def _get_tour(tour_id: str) -> Tournament:
    """Loads a tournament for a change. A finished tournament has to be reopened first."""
    tournament = await Tournament.find_one(Tournament.tour_id == tour_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    if not tournament.active:
        raise HTTPException(status_code=400, detail="The tournament is finished, reopen it to make changes")
    return tournament


@router.get("/isadmin")
async def is_admin(auth: INH_TOKEN_AUTH) -> dict[str, bool]:
    admin = await is_tabletennis_admin(auth)
    return {"is_admin": admin}


@router.get("/get-email")
async def get_email(auth: TABLETENNIS_ADMIN_AUTH, innohassle_id: str) -> dict[str, str]:
    """
    Admin endpoint to fetch a user's email from InNoHassle Accounts using their innohassle_id.
    """
    try:
        acc = await inh_accounts.get_user(innohassle_id=innohassle_id)
        if not acc or not acc.innopolis_info.email:
            raise HTTPException(
                status_code=404, detail=f"User with innohassle_id '{innohassle_id}' not found in InNoHassle Accounts"
            )

        return {"innohassle_id": innohassle_id, "email": acc.innopolis_info.email}

    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to fetch email for ID {innohassle_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal integration error while fetching user data")


@router.get("/get-player")
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
    admin_ids = await tabletennis_admin_ids()

    formatted_players = await asyncio.gather(*(format_player_data(p, admin_ids) for p in players))

    return {"total": len(formatted_players), "players": formatted_players}


@router.get("/active-tours")
async def get_active_tours(auth: INH_TOKEN_AUTH) -> list[dict[str, Any]]:
    """
    Returns a list of all currently active tournaments with details for the frontend:
    metadata, participants (innohassle_ids), and separated game IDs.
    """
    active_tournaments = await Tournament.find(Tournament.active == True).to_list()  # noqa: E712

    result = []
    for tour in active_tournaments:
        val_game_ids = [g.game_id for g in tour.val_games] if tour.val_games else []
        cval_game_ids = [g.game_id for g in tour.cval_games] if tour.cval_games else []

        result.append(
            {
                "id": tour.tour_id,
                "name": tour.name,
                "date": tour.date.isoformat() if tour.date else None,
                "players": tour.players or [],
                "games": {
                    "val_game_ids": val_game_ids,
                    "cval_game_ids": cval_game_ids,
                    "total_count": len(val_game_ids) + len(cval_game_ids),
                },
                "val_top": tour.val_top or {},
                "qual_top": tour.qual_top or {},
                **_tour_stage_data(tour),
            }
        )

    return result


@router.get("/get-tours")
async def get_tours(auth: INH_TOKEN_AUTH) -> list[dict[str, Any]]:
    """
    Returns a list of all tournaments (both active and archived)
    with metadata, participants, and game IDs separated by type.
    """
    tournaments = await Tournament.find_all().to_list()

    result = []
    for tour in tournaments:
        val_game_ids = [g.game_id for g in tour.val_games] if tour.val_games else []
        cval_game_ids = [g.game_id for g in tour.cval_games] if tour.cval_games else []

        result.append(
            {
                "id": tour.tour_id,
                "name": tour.name,
                "date": tour.date.isoformat() if tour.date else None,
                "players": tour.players or [],
                "active": tour.active,
                "games": {
                    "val_game_ids": val_game_ids,
                    "cval_game_ids": cval_game_ids,
                    "total_count": len(val_game_ids) + len(cval_game_ids),
                },
                "val_top": tour.val_top or {},
                "qual_top": tour.qual_top or {},
                **_tour_stage_data(tour),
            }
        )

    result.sort(key=lambda item: str(item["date"] or ""), reverse=True)
    return result


@router.get("/get-games")
async def get_games(auth: INH_TOKEN_AUTH) -> list[dict[str, Any]]:
    """
    Returns a list of all played/registered games from the standalone Game collection.
    """
    games = await Game.find_all().to_list()

    result = []
    for game in games:
        game_dict = game.model_dump(mode="json")

        if "_id" in game_dict:
            game_dict["id"] = game_dict["_id"]
            del game_dict["_id"]

        result.append(game_dict)

    return result


async def _games_summary(games: list[Game]) -> list[dict[str, Any]]:
    """Scores, finished status, both players' current nicknames and ratings, and the tournament of each game."""
    tour_ids = {g.tour_id for g in games}
    tournaments = await Tournament.find({"tour_id": {"$in": list(tour_ids)}}).to_list()
    tournaments_by_id = {t.tour_id: t for t in tournaments}

    player_ids = {g.player1_id for g in games} | {g.player2_id for g in games}
    players = await Player.find({"innohassle_id": {"$in": list(player_ids)}}).to_list()
    players_by_id = {p.innohassle_id: p for p in players}

    def player_summary(p_id: str) -> dict[str, Any]:
        player = players_by_id.get(p_id)
        return {
            "innohassle_id": p_id,
            "nickname": player.nickname if player else None,
            "rating": player.rating if player else None,
            "registered": player is not None,
        }

    result = []
    for game in games:
        tournament = tournaments_by_id.get(game.tour_id)
        result.append(
            {
                "game_id": game.game_id,
                "tour_id": game.tour_id,
                "tournament_name": tournament.name if tournament else None,
                "finished": game.finished,
                # the ObjectId holds the creation time, so older games still get a date
                "created_at": game.id.generation_time.isoformat() if game.id else None,
                "finished_at": game.finished_at.isoformat() if game.finished_at else None,
                "player1": {**player_summary(game.player1_id), "score": game.player1_score},
                "player2": {**player_summary(game.player2_id), "score": game.player2_score},
            }
        )
    return result


@router.get("/get-games-by-id")
async def get_games_by_id(auth: INH_TOKEN_AUTH, ids: Annotated[list[str], Query()]) -> dict[str, Any]:
    """
    Returns detailed info for a list of games by their game_id: scores, finished status,
    both players' current nicknames and ratings, and the tournament they belong to.
    Unknown/not-found ids are reported separately instead of silently dropped.
    """
    games = await Game.find({"game_id": {"$in": ids}}).to_list()
    result = await _games_summary(games)

    found_ids = {g["game_id"] for g in result}
    missing_ids = [i for i in ids if i not in found_ids]

    return {"total_found": len(result), "games": result, "missing_ids": missing_ids}


@router.get("/my-games")
async def get_my_games(auth: INH_TOKEN_AUTH) -> dict[str, Any]:
    """Returns every game of the current player, in the same format as /get-games-by-id."""
    games = await Game.find({"$or": [{"player1_id": auth.innohassle_id}, {"player2_id": auth.innohassle_id}]}).to_list()
    return {"games": await _games_summary(games)}


@router.get("/ping")
def ping(auth: INH_TOKEN_AUTH):
    """
    To check that all is good.
    """
    return "All good."


@router.post("/reg")
async def register_player(auth: INH_TOKEN_AUTH) -> Player:
    """
    Registers the calling user (via token) as a player.
    Idempotent: if already registered, just returns the existing player.
    No custom nickname input - the display name always comes from InNoHassle Accounts,
    with an auto-generated placeholder as a fallback if the account has no name yet.
    """
    player = await Player.find_one(Player.innohassle_id == auth.innohassle_id)
    if player:
        return player

    logger.info(f"Try to make new player, id: {auth.innohassle_id}")

    account_info = await inh_accounts.get_user(innohassle_id=auth.innohassle_id)
    if account_info and account_info.innopolis_info and account_info.innopolis_info.name:
        name_to_display = account_info.innopolis_info.name
    else:
        name_to_display = auth.email.split("@")[0] if auth.email else f"user_{str(uuid.uuid4())[:4]}"

    ancient_date = dtm.datetime(2000, 1, 1, tzinfo=dtm.UTC)
    new_player = Player(
        innohassle_id=auth.innohassle_id,
        nickname=name_to_display,
        rating=RTTF_MIN_START_RATING,
        ratings={dtm.datetime.now(tz=dtm.UTC): RTTF_MIN_START_RATING},
        wins=0,
        losses=0,
        last_game=ancient_date,
    )

    await new_player.insert()
    logger.info(f"New player {new_player.nickname} successfully created!")
    return new_player


@router.post("/set-status")
async def set_status(
    auth: TABLETENNIS_ADMIN_AUTH, innohassle_id: str, status: Literal["beginner", "advanced"]
) -> dict[str, Any]:
    """
    Sets a player's status by innohassle_id. Works in both directions regardless of the rating;
    the automatic promotion at ADVANCED_RATING only happens when the rating crosses it.
    """
    player = await Player.find_one(Player.innohassle_id == innohassle_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    player.status = status.capitalize()
    await player.save()
    return await format_player_data(player)


RTTF_MIN_START_RATING = 100


@router.post("/set-rating")
async def set_rating(auth: TABLETENNIS_ADMIN_AUTH, innohassle_id: str, rating: int) -> dict[str, Any]:
    """
    Admin endpoint to set a player's rating by hand to any value from 0. The change is added to
    the player's rating history; reaching ADVANCED_RATING from below promotes a beginner.
    """
    if rating < 0:
        raise HTTPException(status_code=400, detail="Rating cannot be negative")

    player = await Player.find_one(Player.innohassle_id == innohassle_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    old_rating = player.rating
    player.rating = rating
    _promote_if_crossed(player, old_rating)
    if player.ratings is None:
        player.ratings = {}
    player.ratings[dtm.datetime.now(tz=dtm.UTC)] = rating
    await player.save()

    logger.info(f"Admin {auth.email} set rating of {player.nickname} ({innohassle_id}): {old_rating} -> {rating}")
    return await format_player_data(player)


@router.post("/guests")
async def create_guest(
    auth: TABLETENNIS_ADMIN_AUTH, nickname: str, rating: int = RTTF_MIN_START_RATING
) -> dict[str, Any]:
    """
    Admin endpoint to create a guest for someone who has no account yet. A guest can be added to any
    tournament and plays like a registered player; /merge-guest later hands everything over to the account.
    """
    nickname = nickname.strip()
    if not 2 <= len(nickname) <= 20:
        raise HTTPException(status_code=400, detail="Nickname must be 2 to 20 characters long")
    if rating < 0:
        raise HTTPException(status_code=400, detail="Rating cannot be negative")

    guest = Player(
        innohassle_id=f"guest-{uuid.uuid4().hex[:8]}",
        nickname=nickname,
        rating=rating,
        ratings={dtm.datetime.now(tz=dtm.UTC): rating},
        last_game=dtm.datetime(2000, 1, 1, tzinfo=dtm.UTC),
        placeholder=True,
    )
    await guest.insert()
    logger.info(f"Admin {auth.email} created guest {nickname} ({guest.innohassle_id})")
    return await format_player_data(guest)


TOUR_PLAYER_FIELDS = ("players", "groups", "qual_seeding", "val_top", "qual_top", "val_games", "cval_games")
"Stored tournament fields that reference players by innohassle_id."


def _swap_id(value: Any, old: str, new: str) -> Any:
    if isinstance(value, str):
        return new if value == old else value
    if isinstance(value, list):
        return [_swap_id(v, old, new) for v in value]
    if isinstance(value, dict):
        return {k: _swap_id(v, old, new) for k, v in value.items()}
    return value


@router.post("/merge-guest")
async def merge_guest(
    auth: TABLETENNIS_ADMIN_AUTH, guest_id: str, player_id: str | None = None, email: EmailStr | None = None
) -> dict[str, Any]:
    """
    Admin endpoint to hand a guest over to the registered player it stood for. The player replaces the
    guest in every tournament and game, and the guest is deleted. A player who has not played yet takes
    the guest's rating, status and history; otherwise the rating changes of the guest's games are added.
    """
    guest = await Player.find_one(Player.innohassle_id == guest_id)
    if not guest or not guest.placeholder:
        raise HTTPException(status_code=404, detail="Guest not found")

    target = await resolve_player(player_id=player_id, email=email)
    if not target or target.placeholder:
        raise HTTPException(status_code=404, detail="Registered player not found")
    new_id = target.innohassle_id

    shared = await Tournament.find({"players": {"$all": [guest_id, new_id]}}).to_list()
    if shared:
        raise HTTPException(
            status_code=400,
            detail=f"The guest and the player are in the same tournament: {', '.join(t.name for t in shared)}",
        )

    async def merge(session: AsyncClientSession) -> tuple[Player, int]:
        guest_now = await Player.find_one(Player.innohassle_id == guest_id, session=session)
        player = await Player.find_one(Player.innohassle_id == new_id, session=session)
        if not guest_now or not player:
            raise HTTPException(status_code=404, detail="Guest or player not found")

        tours = Tournament.get_pymongo_collection()
        moved = 0
        async for doc in tours.find({"players": guest_id}, session=session):
            update = {f: _swap_id(doc[f], guest_id, new_id) for f in TOUR_PLAYER_FIELDS if f in doc}
            await tours.update_one({"_id": doc["_id"]}, {"$set": update}, session=session)
            moved += 1

        games = Game.get_pymongo_collection()
        delta = 0
        guest_games = {"$or": [{"player1_id": guest_id}, {"player2_id": guest_id}], "finished": True}
        async for g in games.find(guest_games, session=session):
            delta += (g.get("player1_delta") if g["player1_id"] == guest_id else g.get("player2_delta")) or 0
        await games.update_many({"player1_id": guest_id}, {"$set": {"player1_id": new_id}}, session=session)
        await games.update_many({"player2_id": guest_id}, {"$set": {"player2_id": new_id}}, session=session)

        now = dtm.datetime.now(tz=dtm.UTC)
        if player.wins + player.losses == 0:
            player.rating = guest_now.rating
            player.status = guest_now.status
            player.ratings = {**guest_now.ratings, now: player.rating}
        else:
            old_rating = player.rating
            player.rating = max(0, player.rating + delta)
            _promote_if_crossed(player, old_rating)
            player.ratings[now] = player.rating
        player.wins += guest_now.wins
        player.losses += guest_now.losses
        player.last_game = max(player.last_game, guest_now.last_game)
        await player.save(session=session)
        await guest_now.delete(session=session)
        return player, moved

    player, moved = await _in_transaction(merge)

    logger.info(f"Admin {auth.email} merged guest {guest.nickname} ({guest_id}) into {player.nickname} ({new_id})")
    return {"status": "success", "tournaments": moved, "player": await format_player_data(player)}


@router.post("/reg-tour")
async def register_tour(
    auth: TABLETENNIS_ADMIN_AUTH,
    name: str,
    player_ids: list[str] | None = None,
    emails: list[EmailStr] | None = None,
    date: dtm.datetime | None = None,
) -> dict[str, Any]:
    """
    Creates a new tournament. Players can be specified either by innohassle_id (player_ids)
    or by email (emails) - both lists are optional and can be freely combined.
    Nothing is created unless every given player is found; the 400 response lists the missing ones.
    """
    name = name.strip()
    if not 1 <= len(name) <= 100:
        raise HTTPException(status_code=400, detail="Tournament name must be 1 to 100 characters long")

    valid_players: list[str] = []
    failed_players = await _resolve_players(player_ids or [], emails or [], valid_players, set())

    if failed_players:
        raise HTTPException(
            status_code=400,
            detail={"message": "Some players were not found, the tournament was not created", "failed": failed_players},
        )

    if len(valid_players) < 2:
        raise HTTPException(status_code=400, detail="A tournament needs at least 2 players")

    tour_id = str(uuid.uuid4())[:8]
    new_tournament = Tournament(
        tour_id=tour_id,
        name=name,
        players=valid_players,
        val_games=[],
        cval_games=[],
        active=True,
        date=dtm.datetime.now(tz=dtm.UTC) if not date else date,
        qual_top={},
        val_top={},
    )

    await new_tournament.insert()
    logger.info(f"Tournament '{name}' ({tour_id}) created with {len(valid_players)} players")

    return {"status": "success", "tournament_id": tour_id, "name": name, "added": valid_players}


@router.post("/reg-tour/add-player")
async def add_player(
    auth: TABLETENNIS_ADMIN_AUTH,
    tour_id: str,
    player_ids: list[str] | None = None,
    emails: list[EmailStr] | None = None,
) -> dict[str, Any]:
    """
    Adds multiple players to an ACTIVE tournament, specified either by innohassle_id (player_ids)
    or by email (emails) - both lists are optional and can be freely combined.
    Nobody is added unless every given player can be added; the 400 response lists the failed ones.
    """
    tournament = await Tournament.find_one(Tournament.tour_id == tour_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    if not tournament.active:
        raise HTTPException(status_code=400, detail="Cannot add players to an inactive/archived tournament!")

    if tournament.groups_locked:
        raise HTTPException(status_code=400, detail="Cannot add players: groups are already locked!")

    added_players: list[str] = []
    failed_players = await _resolve_players(
        player_ids or [], emails or [], added_players, set(tournament.players or [])
    )

    if failed_players:
        raise HTTPException(
            status_code=400,
            detail={"message": "Some players cannot be added, nobody was added", "failed": failed_players},
        )

    if added_players:
        # $addToSet: another admin may be adding players at the same time
        await Tournament.get_pymongo_collection().update_one(
            {"tour_id": tour_id}, {"$addToSet": {"players": {"$each": added_players}}}
        )
        logger.info(f"Admin {auth.email} added {len(added_players)} players to tournament {tour_id}")

    return {"status": "success", "tour_id": tour_id, "added": added_players}


@router.post("/reg-tour/remove-players")
async def remove_players(
    auth: TABLETENNIS_ADMIN_AUTH,
    tour_id: str,
    player_ids: list[str] | None = None,
    emails: list[EmailStr] | None = None,
) -> dict[str, Any]:
    """
    Removes multiple players from an ACTIVE tournament, specified either by innohassle_id (player_ids)
    or by email (emails) - both lists are optional and can be freely combined.
    Checks if players exist in the list and ensures they haven't played any games yet.
    """
    tournament = await Tournament.find_one(Tournament.tour_id == tour_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    if not tournament.active:
        raise HTTPException(status_code=400, detail="Cannot remove players from an inactive/archived tournament!")

    if tournament.groups_locked:
        raise HTTPException(status_code=400, detail="Cannot remove players: groups are already locked!")

    if not tournament.players:
        tournament.players = []

    player_ids = player_ids or []
    emails = emails or []

    removed_players: list[str] = []
    failed_players: list[dict[str, str]] = []

    def has_games(p_id: str) -> bool:
        for list_name in ["val_games", "cval_games"]:
            games_list = getattr(tournament, list_name)
            if games_list:
                for game in games_list:
                    if game.player1_id == p_id or game.player2_id == p_id:
                        return True
        return False

    async def try_remove(identifier: str, player: Player | None, not_found_reason: str) -> None:
        if not player:
            failed_players.append({"identifier": identifier, "reason": not_found_reason})
            return

        p_id = player.innohassle_id
        if p_id not in tournament.players:
            failed_players.append(
                {"identifier": identifier, "reason": "Player is not in this tournament's participant list"}
            )
            return

        if has_games(p_id):
            failed_players.append(
                {
                    "identifier": identifier,
                    "reason": "Cannot remove player: they already have generated games in this tournament!",
                }
            )
            return

        tournament.players.remove(p_id)
        for members in (tournament.groups or {}).values():
            if p_id in members:
                members.remove(p_id)
        removed_players.append(p_id)

    for p_id in player_ids:
        player = await resolve_player(player_id=p_id)
        await try_remove(p_id, player, "Player is not registered in table tennis system")

    for email in emails:
        player = await resolve_player(email=email)
        await try_remove(email, player, "User not found in InNoHassle Accounts or not registered via /reg")

    if removed_players:
        await _set_tour_fields(tournament, players=tournament.players, groups=tournament.groups or {})
        logger.info(
            f"Admin {auth.email} removed {len(removed_players)} players from tournament {tour_id}. "
            f"Failed/Skipped: {len(failed_players)}."
        )

    return {
        "status": "partial_success"
        if failed_players and removed_players
        else ("success" if removed_players else "failed"),
        "tour_id": tour_id,
        "removed_count": len(removed_players),
        "failed_count": len(failed_players),
        "removed": removed_players,
        "failed": failed_players,
    }


@router.post("/reg-tour/change-val-top")
async def change_val_top(
    auth: TABLETENNIS_ADMIN_AUTH,
    tour_id: str,
    top: Annotated[
        dict[int, str],
        Body(
            description="Full place->innohassle_id mapping, e.g. {1: 'id_1st_place', 2: 'id_2nd_place'}. Overwrites completely."
        ),
    ],
) -> dict[str, Any]:
    """
    Admin endpoint to fully overwrite a tournament's val_top (final-stage standings).
    This is NOT a patch - the frontend sends the complete standings each time and it
    replaces whatever was stored before. Every player in the mapping must already be
    a participant of the tournament, and each player may occupy only one place.
    """
    tournament = await _get_tour(tour_id)

    _validate_top(tournament, top)

    await _set_tour_fields(tournament, val_top=top)

    logger.info(f"Admin {auth.email} set val_top for tournament {tour_id}: {top}")

    return {"status": "success", "tour_id": tour_id, "val_top": await format_top(top)}


@router.post("/reg-tour/change-qual-top")
async def change_qual_top(
    auth: TABLETENNIS_ADMIN_AUTH,
    tour_id: str,
    top: Annotated[
        dict[int, str],
        Body(
            description="Full place->innohassle_id mapping, e.g. {1: 'id_1st_place', 2: 'id_2nd_place'}. Overwrites completely."
        ),
    ],
) -> dict[str, Any]:
    """
    Admin endpoint to fully overwrite a tournament's qual_top (qualification-stage standings).
    Same semantics as change-val-top: full overwrite, not a patch.
    """
    tournament = await _get_tour(tour_id)

    _validate_top(tournament, top)

    await _set_tour_fields(tournament, qual_top=top)

    await _apply_tournament_bonuses(tournament)

    logger.info(f"Admin {auth.email} set qual_top for tournament {tour_id}: {top}")

    return {"status": "success", "tour_id": tour_id, "qual_top": await format_top(top)}


@router.post("/reg-tour/set-groups")
async def set_groups(
    auth: TABLETENNIS_ADMIN_AUTH,
    tour_id: str,
    groups: Annotated[
        dict[str, list[str]],
        Body(description="Full group name->innohassle_ids mapping, e.g. {'A': ['id1', 'id2']}. Overwrites completely."),
    ],
) -> dict[str, Any]:
    """
    Admin endpoint to fully overwrite the validation-stage groups of an ACTIVE tournament.
    Groups can have any size and may be changed freely until they are locked.
    """
    tournament = await Tournament.find_one(Tournament.tour_id == tour_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    if not tournament.active:
        raise HTTPException(status_code=400, detail="Cannot change groups of an inactive/archived tournament!")

    if tournament.groups_locked:
        raise HTTPException(status_code=400, detail="Groups are already locked!")

    _validate_groups(tournament, groups)

    await _set_tour_fields(tournament, groups=groups)

    logger.info(f"Admin {auth.email} set groups for tournament {tour_id}: {groups}")
    return {"status": "success", "tour_id": tour_id, **_tour_stage_data(tournament)}


@router.post("/reg-tour/lock-groups")
async def lock_groups(auth: TABLETENNIS_ADMIN_AUTH, tour_id: str) -> dict[str, Any]:
    """
    Admin endpoint to lock the groups. Every participant must be in a group and every
    group must have at least 2 players. After locking, validation games can be started.
    """
    tournament = await _get_tour(tour_id)

    if not tournament.groups:
        raise HTTPException(status_code=400, detail="Create groups first")

    _validate_groups(tournament, tournament.groups)

    grouped = {p_id for members in tournament.groups.values() for p_id in members}
    ungrouped = [p_id for p_id in tournament.players or [] if p_id not in grouped]
    if ungrouped:
        raise HTTPException(
            status_code=400, detail={"message": "Some players are not in any group", "ungrouped": ungrouped}
        )

    small_groups = [name for name, members in tournament.groups.items() if len(members) < 2]
    if small_groups:
        raise HTTPException(status_code=400, detail=f"Every group needs at least 2 players: {small_groups}")

    await _set_tour_fields(tournament, groups_locked=True)

    logger.info(f"Admin {auth.email} locked groups for tournament {tour_id}")
    return {"status": "success", "tour_id": tour_id, **_tour_stage_data(tournament)}


@router.post("/reg-tour/unlock-groups")
async def unlock_groups(auth: TABLETENNIS_ADMIN_AUTH, tour_id: str) -> dict[str, Any]:
    """
    Admin endpoint to unlock the groups again. Only possible while no validation games exist.
    """
    tournament = await _get_tour(tour_id)

    if tournament.val_games:
        raise HTTPException(status_code=400, detail="Cannot unlock groups: validation games have already started")

    await _set_tour_fields(tournament, groups_locked=False)

    logger.info(f"Admin {auth.email} unlocked groups for tournament {tour_id}")
    return {"status": "success", "tour_id": tour_id, **_tour_stage_data(tournament)}


@router.post("/reg-tour/set-qual-seeding")
async def set_qual_seeding(
    auth: TABLETENNIS_ADMIN_AUTH,
    tour_id: str,
    seeding: Annotated[
        list[str], Body(description="All participants' innohassle_ids ordered from the 1st seed to the last.")
    ],
) -> dict[str, Any]:
    """
    Admin endpoint to fix the qualification bracket seeding, which starts the qualification.
    The seeding must contain every participant exactly once and cannot be changed once
    qualification games exist.
    """
    tournament = await _get_tour(tour_id)

    if tournament.cval_games:
        raise HTTPException(status_code=400, detail="Qualification games have already started")

    if tournament.groups and not tournament.groups_locked:
        raise HTTPException(status_code=400, detail="Lock the groups first")

    if any(not g.finished for g in tournament.val_games or []):
        raise HTTPException(status_code=400, detail="Finish or cancel the group games in progress first")

    if len(seeding) < 2:
        raise HTTPException(status_code=400, detail="At least 2 players are needed for qualification")

    if len(set(seeding)) != len(seeding) or set(seeding) != set(tournament.players or []):
        raise HTTPException(status_code=400, detail="Seeding must contain every participant exactly once")

    await _set_tour_fields(tournament, qual_seeding=seeding)

    logger.info(f"Admin {auth.email} set qualification seeding for tournament {tour_id}: {seeding}")
    return {"status": "success", "tour_id": tour_id, **_tour_stage_data(tournament)}


@router.post("/finish-tour")
async def finish_tournament(auth: TABLETENNIS_ADMIN_AUTH, tour_id: str) -> dict[str, Any]:
    """
    Admin endpoint to close/archive a tournament.
    """
    tournament = await Tournament.find_one(Tournament.tour_id == tour_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    if not tournament.active:
        return {"status": "warning", "message": "Tournament is already archived"}

    await _set_tour_fields(tournament, active=False)

    logger.info(f"Tournament '{tournament.name}' ({tour_id}) has been archived by admin {auth.email}")
    return {"status": "success", "message": f"Tournament {tour_id} successfully closed"}


@router.post("/delete-tour")
async def delete_tournament(auth: TABLETENNIS_ADMIN_AUTH, tour_id: str) -> dict[str, Any]:
    """
    Admin endpoint to delete a tournament created by mistake. Only possible while no game in it
    is finished, so ratings are never affected; unfinished games are deleted with it.
    """
    tournament = await Tournament.find_one(Tournament.tour_id == tour_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    async def delete(session: AsyncClientSession) -> None:
        removed = await Tournament.get_pymongo_collection().delete_one(
            {
                "tour_id": tour_id,
                "val_games": {"$not": {"$elemMatch": {"finished": True}}},
                "cval_games": {"$not": {"$elemMatch": {"finished": True}}},
            },
            session=session,
        )
        if removed.deleted_count == 0:
            raise HTTPException(status_code=400, detail="A tournament with finished games cannot be deleted")
        await Game.get_pymongo_collection().delete_many({"tour_id": tour_id}, session=session)

    await _in_transaction(delete)

    logger.info(f"Tournament '{tournament.name}' ({tour_id}) has been deleted by admin {auth.email}")
    return {"status": "success", "tour_id": tour_id}


@router.post("/reopen-tour")
async def reopen_tournament(auth: TABLETENNIS_ADMIN_AUTH, tour_id: str) -> dict[str, Any]:
    """
    Admin endpoint to make an archived tournament active again, so its games and standings can be corrected.
    Bonuses are still granted at most once.
    """
    tournament = await Tournament.find_one(Tournament.tour_id == tour_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    if tournament.active:
        raise HTTPException(status_code=400, detail="Tournament is already active")

    await _set_tour_fields(tournament, active=True)

    logger.info(f"Tournament '{tournament.name}' ({tour_id}) has been reopened by admin {auth.email}")
    return {"status": "success", "tour_id": tour_id}


@router.post("/reg-game")
async def register_game(
    auth: TABLETENNIS_ADMIN_AUTH,
    tour_id: str,
    tip: Literal["val", "cval"],
    player1_id: str | None = None,
    player1_email: EmailStr | None = None,
    player2_id: str | None = None,
    player2_email: EmailStr | None = None,
) -> dict[str, Any]:
    """
    Creates a new game in a tournament with start score 0:0.
    Each of the two players can be identified either by innohassle_id or by email
    (for player1: player1_id or player1_email; for player2: player2_id or player2_email).
    """
    p1 = await resolve_player(player_id=player1_id, email=player1_email)
    p2 = await resolve_player(player_id=player2_id, email=player2_email)

    if not p1 or not p2:
        raise HTTPException(status_code=404, detail="One or both players are not registered in the system (/reg)")

    if p1.innohassle_id == p2.innohassle_id:
        raise HTTPException(status_code=400, detail="A player cannot play a match against themselves!")

    tournament = await _get_tour(tour_id)

    if p1.innohassle_id not in tournament.players or p2.innohassle_id not in tournament.players:
        raise HTTPException(status_code=400, detail="One or both players are not in this tournament's player list")

    if tip == "val" and tournament.groups:
        if not tournament.groups_locked:
            raise HTTPException(status_code=400, detail="Lock the groups before starting validation games")
        if tournament.qual_seeding:
            raise HTTPException(status_code=400, detail="Qualification has already started")
        group1 = _find_player_group(tournament, p1.innohassle_id)
        group2 = _find_player_group(tournament, p2.innohassle_id)
        if group1 is None or group1 != group2:
            raise HTTPException(status_code=400, detail="Validation games are played only inside one group")

    game_id = str(uuid.uuid4())[:8]
    new_game = Game(
        tour_id=tour_id,
        game_id=game_id,
        player1_id=p1.innohassle_id,
        player2_id=p2.innohassle_id,
        player1_score=0,
        player2_score=0,
        finished=False,
    )
    field = "val_games" if tip == "val" else "cval_games"
    a, b = p1.innohassle_id, p2.innohassle_id
    same_pair = {"$or": [{"player1_id": a, "player2_id": b}, {"player1_id": b, "player2_id": a}]}

    # atomic push that also refuses a second game for the same pair in this stage
    # (two admins pressing "start" at the same time must not create two games)
    push = await Tournament.get_pymongo_collection().update_one(
        {"tour_id": tour_id, field: {"$not": {"$elemMatch": same_pair}}},
        {"$push": {field: _embedded_game(new_game)}},
    )
    if push.matched_count == 0:
        raise HTTPException(status_code=409, detail="These players already have a game in this stage of the tournament")

    await new_game.insert()
    logger.info(f"Game between {p1.nickname} and {p2.nickname} registered in tournament {tour_id}")

    return {
        "status": "success",
        "message": "Game successfully registered in tournament",
        "game_id": str(new_game.game_id),
    }


@router.post("/finish-game")
async def finish_game(auth: TABLETENNIS_ADMIN_AUTH, game_id: str, s1: int, s2: int, tour_id: str) -> dict[str, Any]:
    """
    Admin endpoint to record a match result using game_id and tour_id.
    Calculates Elo, updates player stats, and synchronizes scores inside the tournament.
    Refuses to recalculate rating for a game that was already finished.
    """
    _validate_score(s1, s2)

    tournament = await _get_tour(tour_id)

    located = _find_tour_game(tournament, game_id)
    if not located:
        raise HTTPException(status_code=404, detail="Game not found in this tournament")
    field, target_game = located

    if field == "val_games" and tournament.qual_seeding:
        raise HTTPException(status_code=400, detail="Group games cannot be finished after qualification started")

    if target_game.finished:
        raise HTTPException(
            status_code=400,
            detail="This game has already been finished. Recalculating rating is not allowed.",
        )

    async def record(session: AsyncClientSession) -> tuple[Player, Player, int, int]:
        # players are read inside the transaction: a concurrent game of the same player
        # makes it retry with the fresh rating instead of overwriting it
        p1 = await Player.find_one(Player.innohassle_id == target_game.player1_id, session=session)
        p2 = await Player.find_one(Player.innohassle_id == target_game.player2_id, session=session)
        if not p1 or not p2:
            raise HTTPException(status_code=404, detail="One or both players from this game are not registered (/reg)")

        if s1 > s2:
            delta_1, delta_2 = await _apply_rttf_delta(p1, p2, s1, s2, tournament)
        else:
            delta_2, delta_1 = await _apply_rttf_delta(p2, p1, s2, s1, tournament)

        current_time = dtm.datetime.now(tz=dtm.UTC)
        delta_1, delta_2, promoted_1, promoted_2 = _apply_result_to_players(p1, p2, s1, s2, delta_1, delta_2)
        for player in (p1, p2):
            player.last_game = current_time
            if player.ratings is None:
                player.ratings = {}
            player.ratings[current_time] = player.rating
        await p1.save(session=session)
        await p2.save(session=session)

        # claim the unfinished game last: if two admins finish it at the same time, only one
        # transaction commits, the other one is rolled back together with its rating changes
        result_fields = {
            "finished": True,
            "finished_at": current_time,
            "player1_score": s1,
            "player2_score": s2,
            "player1_delta": delta_1,
            "player2_delta": delta_2,
            "player1_promoted": promoted_1,
            "player2_promoted": promoted_2,
        }
        claim = await Tournament.get_pymongo_collection().update_one(
            {"tour_id": tour_id, field: {"$elemMatch": {"game_id": game_id, "finished": False}}},
            {"$set": {f"{field}.$.{k}": v for k, v in result_fields.items()}},
            session=session,
        )
        if claim.modified_count == 0:
            raise HTTPException(
                status_code=400,
                detail="This game has already been finished. Recalculating rating is not allowed.",
            )
        await Game.get_pymongo_collection().update_one({"game_id": game_id}, {"$set": result_fields}, session=session)
        return p1, p2, delta_1, delta_2

    p1, p2, delta_1, delta_2 = await _in_transaction(record)

    logger.info(
        f"Match {game_id} in tour {tour_id} saved by admin {auth.email}: {p1.nickname} ({s1}) vs {p2.nickname} ({s2}). "
        f"RTTF: {p1.nickname} ({'+' if delta_1 >= 0 else ''}{delta_1}), {p2.nickname} ({'+' if delta_2 >= 0 else ''}{delta_2})"
    )

    return {
        "status": "success",
        "game_id": game_id,
        "player1": {"nickname": p1.nickname, "new_rating": p1.rating, "delta": delta_1, "league": p1.status},
        "player2": {"nickname": p2.nickname, "new_rating": p2.rating, "delta": delta_2, "league": p2.status},
    }


@router.post("/fix-game")
async def fix_game(auth: TABLETENNIS_ADMIN_AUTH, game_id: str, s1: int, s2: int, tour_id: str) -> dict[str, Any]:
    """
    Admin endpoint to correct the score of an already finished game in an ACTIVE tournament.
    The rating change of the old result is rolled back and the new result is applied.
    Group (val) games cannot be corrected once qualification has started, because the seeding is fixed.
    """
    _validate_score(s1, s2)

    tournament = await Tournament.find_one(Tournament.tour_id == tour_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    if not tournament.active:
        raise HTTPException(status_code=400, detail="Cannot correct games of an inactive/archived tournament!")

    located = _find_tour_game(tournament, game_id)
    if not located:
        raise HTTPException(status_code=404, detail="Game not found in this tournament")
    field, game = located

    if not game.finished:
        raise HTTPException(status_code=400, detail="This game is not finished yet")

    if field == "val_games" and tournament.qual_seeding:
        raise HTTPException(status_code=400, detail="Group games cannot be corrected after qualification started")

    if game.player1_delta is None or game.player2_delta is None:
        raise HTTPException(status_code=400, detail="This game was finished before score corrections were supported")

    old_s1, old_s2 = game.player1_score, game.player2_score
    if (old_s1, old_s2) == (s1, s2):
        return {"status": "success", "game_id": game_id, "changed": False}

    if field == "cval_games" and (old_s1 > old_s2) != (s1 > s2):
        cval_games = tournament.cval_games or []
        later = cval_games[[g.game_id for g in cval_games].index(game_id) + 1 :]
        pair = {game.player1_id, game.player2_id}
        if any(g.player1_id in pair or g.player2_id in pair for g in later):
            raise HTTPException(
                status_code=400,
                detail="The winner cannot change: the next qualification match of these players has already started",
            )

    async def correct(session: AsyncClientSession) -> tuple[Player, Player, int, int]:
        p1 = await Player.find_one(Player.innohassle_id == game.player1_id, session=session)
        p2 = await Player.find_one(Player.innohassle_id == game.player2_id, session=session)
        if not p1 or not p2:
            raise HTTPException(status_code=404, detail="One or both players from this game are not registered (/reg)")

        _undo_result_of_players(p1, p2, old_s1, old_s2, game)

        if s1 > s2:
            delta_1, delta_2 = await _apply_rttf_delta(p1, p2, s1, s2, tournament)
        else:
            delta_2, delta_1 = await _apply_rttf_delta(p2, p1, s2, s1, tournament)

        delta_1, delta_2, promoted_1, promoted_2 = _apply_result_to_players(p1, p2, s1, s2, delta_1, delta_2)
        current_time = dtm.datetime.now(tz=dtm.UTC)
        for player in (p1, p2):
            if player.ratings is None:
                player.ratings = {}
            player.ratings[current_time] = player.rating
        await p1.save(session=session)
        await p2.save(session=session)

        result_fields = {
            "player1_score": s1,
            "player2_score": s2,
            "player1_delta": delta_1,
            "player2_delta": delta_2,
            "player1_promoted": promoted_1,
            "player2_promoted": promoted_2,
        }
        # optimistic lock on the old score: a concurrent correction must not roll back the rating twice
        claim = await Tournament.get_pymongo_collection().update_one(
            {
                "tour_id": tour_id,
                field: {
                    "$elemMatch": {
                        "game_id": game_id,
                        "finished": True,
                        "player1_score": old_s1,
                        "player2_score": old_s2,
                    }
                },
            },
            {"$set": {f"{field}.$.{k}": v for k, v in result_fields.items()}},
            session=session,
        )
        if claim.modified_count == 0:
            raise HTTPException(status_code=409, detail="This game was changed by someone else, reload and try again")
        await Game.get_pymongo_collection().update_one({"game_id": game_id}, {"$set": result_fields}, session=session)
        return p1, p2, delta_1, delta_2

    p1, p2, delta_1, delta_2 = await _in_transaction(correct)

    logger.info(
        f"Match {game_id} in tour {tour_id} corrected by admin {auth.email}: {old_s1}:{old_s2} -> {s1}:{s2}. "
        f"New RTTF deltas: {p1.nickname} ({delta_1}), {p2.nickname} ({delta_2})"
    )

    return {
        "status": "success",
        "game_id": game_id,
        "changed": True,
        "player1": {"nickname": p1.nickname, "new_rating": p1.rating, "delta": delta_1},
        "player2": {"nickname": p2.nickname, "new_rating": p2.rating, "delta": delta_2},
    }


@router.post("/cancel-game")
async def cancel_game(auth: TABLETENNIS_ADMIN_AUTH, game_id: str, tour_id: str) -> dict[str, Any]:
    """
    Admin endpoint to delete a game that was started by mistake. Only unfinished games can be
    cancelled, so ratings are never affected.
    """
    tournament = await _get_tour(tour_id)

    located = _find_tour_game(tournament, game_id)
    if not located:
        raise HTTPException(status_code=404, detail="Game not found in this tournament")
    field, game = located

    if game.finished:
        raise HTTPException(status_code=400, detail="A finished game cannot be cancelled, correct its score instead")

    pull = await Tournament.get_pymongo_collection().update_one(
        {"tour_id": tour_id}, {"$pull": {field: {"game_id": game_id, "finished": False}}}
    )
    if pull.modified_count == 0:
        raise HTTPException(status_code=400, detail="A finished game cannot be cancelled, correct its score instead")

    await Game.get_pymongo_collection().delete_one({"game_id": game_id, "finished": False})

    logger.info(f"Game {game_id} in tour {tour_id} cancelled by admin {auth.email}")
    return {"status": "success", "game_id": game_id}
