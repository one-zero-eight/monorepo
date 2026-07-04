from src.logging_ import logger
from src.schedule.modules.event_groups.repository import event_group_repository
from src.schedule.modules.predefined.storage import JsonPredefinedUsers
from src.schedule.modules.users.repository import user_repository


class PredefinedRepository:
    storage: JsonPredefinedUsers

    def update_storage(self, storage: JsonPredefinedUsers):
        self.storage = storage

    async def get_user_predefined(self, user_id: int) -> list[int]:
        user = await user_repository.read(user_id)
        if user is None:
            return []
        predefind_user = self.storage.get_user(user.email)
        group_aliases = []

        if predefind_user:
            group_aliases.extend(predefind_user.groups)

        groups = self.storage.get_academic_groups(user.email)
        for group in groups:
            if group.event_group_alias:
                group_aliases.append(group.event_group_alias)

        if not group_aliases:
            return []

        event_group_mapping = await event_group_repository.batch_read_ids_by_aliases(group_aliases)
        if None in event_group_mapping.values():
            logger.warning(f"User {user.email} has invalid predefined groups: {group_aliases}")
        return list(filter(None, event_group_mapping.values()))


predefined_repository: PredefinedRepository = PredefinedRepository()
