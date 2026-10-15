from src.schedule.config import settings
from src.schedule.modules.predefined.storage import JsonPredefinedUsers
from src.schedule.modules.schedule_assistant.client import schedule_assistant_client


class PredefinedRepository:
    storage: JsonPredefinedUsers

    def update_storage(self, storage: JsonPredefinedUsers):
        self.storage = storage

    async def get_user_predefined(self, email: str) -> list[str]:
        predefind_user = self.storage.get_user(email)
        group_aliases = []

        if predefind_user:
            group_aliases.extend(predefind_user.groups)

        groups = self.storage.get_academic_groups(email)
        for group in groups:
            if group.event_group_alias:
                group_aliases.append(group.event_group_alias)

        if settings.schedule_assistant is not None:
            group_aliases.extend(await schedule_assistant_client.get_user_predefined(email))

        return list(dict.fromkeys(group_aliases))


predefined_repository: PredefinedRepository = PredefinedRepository()
