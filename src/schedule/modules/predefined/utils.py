from src.schedule.config import settings
from src.schedule.modules.predefined.storage import JsonPredefinedUsers


def setup_predefined_data_from_object(user_storage: JsonPredefinedUsers):
    from src.schedule.modules.predefined.repository import predefined_repository

    predefined_repository.update_storage(user_storage)
    # also save to file
    users_path = settings.predefined_dir / "innopolis_user_data.json"
    users_path.parent.mkdir(parents=True, exist_ok=True)
    with users_path.open("w", encoding="utf-8") as users_file:
        users_file.write(user_storage.model_dump_json(indent=2))
