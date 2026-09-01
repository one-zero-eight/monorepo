from src.schedule.config import settings
from src.schedule.modules.predefined.storage import JsonPredefinedUsers
from src.schedule.modules.schedule_assistant.client import schedule_assistant_client
from src.schedule.modules.users.repository import user_repository


class PredefinedRepository:
    storage: JsonPredefinedUsers

    def update_storage(self, storage: JsonPredefinedUsers):
        self.storage = storage

    async def get_user_predefined(self, user_id: int) -> list[str]:
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

        if settings.schedule_assistant is not None:
            group_aliases.extend(await schedule_assistant_client.get_user_predefined(user.email))

        return list(dict.fromkeys(group_aliases))


predefined_repository: PredefinedRepository = PredefinedRepository()
