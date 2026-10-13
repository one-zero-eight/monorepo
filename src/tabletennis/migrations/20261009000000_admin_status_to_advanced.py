"""
"Admin" used to be a player status. Being an admin is now decided only by the settings
(admin_emails), so players that had this status become Advanced.
"""

from beanie import free_fall_migration

from src.tabletennis.mongo import Player


class Forward:
    @free_fall_migration(document_models=[Player])
    async def admin_status_to_advanced(self, session):
        await Player.get_pymongo_collection().update_many(
            {"status": {"$regex": "^admin$", "$options": "i"}},
            {"$set": {"status": "Advanced"}},
            session=session,
        )


class Backward:
    pass
