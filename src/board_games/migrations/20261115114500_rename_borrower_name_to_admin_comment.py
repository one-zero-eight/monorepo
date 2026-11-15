"""
The reservation field for the admin note used to be called "borrower_name" and stored
the name of the person who took the board game. It is now an optional admin comment.
"""

from beanie import free_fall_migration

from src.board_games.mongo import Reservation


class Forward:
    @free_fall_migration(document_models=[Reservation])
    async def rename_borrower_name_to_admin_comment(self, session):
        await Reservation.get_pymongo_collection().update_many(
            {"borrower_name": {"$exists": True}},
            {"$rename": {"borrower_name": "admin_comment"}},
            session=session,
        )


class Backward:
    @free_fall_migration(document_models=[Reservation])
    async def rename_borrower_name_to_admin_comment(self, session):
        await Reservation.get_pymongo_collection().update_many(
            {"admin_comment": {"$exists": True}},
            {"$rename": {"admin_comment": "borrower_name"}},
            session=session,
        )
