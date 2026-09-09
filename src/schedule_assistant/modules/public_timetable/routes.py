from fastapi import APIRouter

from src.schedule_assistant.modules.public_timetable.schemas import PublicTimetable
from src.schedule_assistant.modules.schedule_config import repository

router = APIRouter(tags=["Public timetable"])


@router.get("/timetable")
async def get_timetable() -> PublicTimetable:
    """Read the timetable anonymously, without membership or scheduler-private data."""
    return PublicTimetable.model_validate(repository.schedule_config_repository.get_assembled())
