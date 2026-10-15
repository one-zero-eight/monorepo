from fastapi import APIRouter

from src.schedule_assistant.dependencies import ScheduleConfigRepoDep
from src.schedule_assistant.modules.public_timetable.schemas import PublicTimetable

router = APIRouter(tags=["Public timetable"])


@router.get("/timetable")
async def get_timetable(config_repo: ScheduleConfigRepoDep) -> PublicTimetable:
    """Read the timetable anonymously, without membership or scheduler-private data."""
    return PublicTimetable.model_validate(config_repo.get_assembled())
