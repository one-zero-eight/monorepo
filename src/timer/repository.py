from src.timer.db.models import Timer, TimerCheckpoint, TimerParticipant, TimerPermission, TimerUserType
from src.timer.db.storage import SQLAlchemyStorage
from src.timer.schemas import CreateTimer, ViewTimer


async def create_timer(storage: SQLAlchemyStorage, data: CreateTimer, creator_id: str) -> ViewTimer:
    timer = Timer(
        title=data.title,
        start_time=data.start_time,
        end_time=data.end_time,
        checkpoints=[
            TimerCheckpoint(title=checkpoint.title, time=checkpoint.time)
            for checkpoint in sorted(data.checkpoints, key=lambda checkpoint: checkpoint.time)
        ],
        participants=[
            TimerParticipant(
                user_id=creator_id,
                user_type=TimerUserType.CREATOR,
                permissions=[TimerPermission.UPDATE, TimerPermission.DELETE],
            )
        ],
    )
    async with storage.create_session() as session, session.begin():
        session.add(timer)
        await session.flush()
        result = ViewTimer.model_validate(timer)
    return result
