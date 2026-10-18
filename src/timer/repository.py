from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.timer.db.models import Invitation, Timer, TimerParticipant, TimerPermission, TimerUserType
from src.timer.db.storage import SQLAlchemyStorage
from src.timer.schemas import CreateTimer, UpdateTimer, ViewInvitation, ViewTimer


class TimerNotFoundError(Exception):
    pass


class TimerUpdateForbiddenError(Exception):
    pass


class TimerDeleteForbiddenError(Exception):
    pass


class TimerInviteForbiddenError(Exception):
    pass


class InvitationNotFoundError(Exception):
    pass


async def _lock_timer_and_participant(session: AsyncSession, timer_id: int, user_id: str) -> TimerParticipant:
    # All writes lock the timer first, so deletion's participant cascade cannot invert the lock order.
    found_id = await session.scalar(select(Timer.id).where(Timer.id == timer_id).with_for_update())
    if found_id is None:
        raise TimerNotFoundError
    participant = await session.scalar(
        select(TimerParticipant)
        .where(TimerParticipant.timer_id == timer_id, TimerParticipant.user_id == user_id)
        .with_for_update()
    )
    if participant is None:
        raise TimerNotFoundError
    return participant


async def list_timers(storage: SQLAlchemyStorage, user_id: str) -> list[ViewTimer]:
    query = (
        select(Timer)
        .join(TimerParticipant, TimerParticipant.timer_id == Timer.id)
        .where(TimerParticipant.user_id == user_id)
        .options(selectinload(Timer.participants))
        .order_by(Timer.created_at.desc(), Timer.id.desc())
    )
    async with storage.create_session() as session:
        timers = await session.scalars(query)
        return [ViewTimer.model_validate(timer) for timer in timers]


async def get_timer(storage: SQLAlchemyStorage, timer_id: int, user_id: str) -> ViewTimer | None:
    query = (
        select(TimerParticipant)
        .where(TimerParticipant.timer_id == timer_id, TimerParticipant.user_id == user_id)
        .options(
            joinedload(TimerParticipant.timer, innerjoin=True).joinedload(Timer.participants),
        )
    )
    async with storage.create_session() as session:
        result = await session.execute(query)
        participant = result.unique().scalar_one_or_none()
        return ViewTimer.model_validate(participant.timer) if participant is not None else None


async def create_timer(storage: SQLAlchemyStorage, data: CreateTimer, creator_id: str) -> ViewTimer:
    timer = Timer(
        title=data.title,
        start_time=data.start_time,
        end_time=data.end_time,
        checkpoints=[
            checkpoint.model_dump(mode="json")
            for checkpoint in sorted(data.checkpoints, key=lambda checkpoint: checkpoint.time)
        ],
        participants=[
            TimerParticipant(
                user_id=creator_id,
                user_type=TimerUserType.CREATOR,
                permissions=[TimerPermission.UPDATE, TimerPermission.DELETE, TimerPermission.INVITE],
            )
        ],
    )
    async with storage.create_session() as session, session.begin():
        session.add(timer)
        await session.flush()
        result = ViewTimer.model_validate(timer)
    return result


async def update_timer(storage: SQLAlchemyStorage, timer_id: int, user_id: str, data: UpdateTimer) -> ViewTimer:
    async with storage.create_session() as session, session.begin():
        participant = await _lock_timer_and_participant(session, timer_id, user_id)
        if TimerPermission.UPDATE not in participant.permissions:
            raise TimerUpdateForbiddenError

        timer = await session.scalar(
            select(Timer).where(Timer.id == timer_id).options(selectinload(Timer.participants))
        )
        if timer is None:
            raise TimerNotFoundError
        timer.title = data.title
        timer.start_time = data.start_time
        timer.end_time = data.end_time
        timer.checkpoints = [
            checkpoint.model_dump(mode="json")
            for checkpoint in sorted(data.checkpoints, key=lambda checkpoint: checkpoint.time)
        ]
        timer.updated_at = func.now()
        await session.flush()
        await session.refresh(timer, ["updated_at"])
        result = ViewTimer.model_validate(timer)
    return result


async def delete_timer(storage: SQLAlchemyStorage, timer_id: int, user_id: str) -> None:
    async with storage.create_session() as session, session.begin():
        participant = await _lock_timer_and_participant(session, timer_id, user_id)
        if TimerPermission.DELETE not in participant.permissions:
            raise TimerDeleteForbiddenError
        await session.execute(delete(Timer).where(Timer.id == timer_id))


async def create_invitation(storage: SQLAlchemyStorage, timer_id: int, user_id: str) -> ViewInvitation:
    async with storage.create_session() as session, session.begin():
        participant = await _lock_timer_and_participant(session, timer_id, user_id)
        if participant.user_type != TimerUserType.CREATOR or TimerPermission.INVITE not in participant.permissions:
            raise TimerInviteForbiddenError
        invitation = Invitation(timer_id=timer_id)
        session.add(invitation)
        await session.flush()
        result = ViewInvitation.model_validate(invitation)
    return result


async def join_timer(storage: SQLAlchemyStorage, invitation_uuid: UUID, user_id: str) -> ViewTimer:
    async with storage.create_session() as session, session.begin():
        timer = await session.scalar(
            select(Timer)
            .join(Invitation, Invitation.timer_id == Timer.id)
            .where(Invitation.uuid == invitation_uuid)
            .with_for_update(of=Timer)
        )
        if timer is None:
            raise InvitationNotFoundError
        participant = await session.scalar(
            select(TimerParticipant)
            .where(TimerParticipant.timer_id == timer.id, TimerParticipant.user_id == user_id)
            .with_for_update()
        )
        if participant is None:
            session.add(
                TimerParticipant(
                    timer_id=timer.id,
                    user_id=user_id,
                    user_type=TimerUserType.PARTICIPANT,
                    permissions=[TimerPermission.UPDATE],
                )
            )
            await session.flush()
        await session.refresh(timer, ["participants"])
        result = ViewTimer.model_validate(timer)
    return result
