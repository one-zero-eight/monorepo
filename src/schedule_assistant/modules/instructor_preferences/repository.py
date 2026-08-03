import datetime as dtm
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.schedule_assistant.db.models import PreferenceInviteLinkRow
from src.schedule_assistant.db.session import get_engine
from src.schedule_assistant.utcnow import utcnow

INVITE_KEY_BYTES = 8
INVITE_TTL = dtm.timedelta(days=30)


class PreferenceInviteRepository:
    def __init__(self, db_url: str | None = None) -> None:
        self._session_factory: sessionmaker[Session] = sessionmaker(
            bind=get_engine(db_url),
            autoflush=False,
            autocommit=False,
        )

    def _session(self) -> Session:
        return self._session_factory()

    def get_active_by_key(self, key: str) -> PreferenceInviteLinkRow | None:
        now = utcnow()
        with self._session() as session:
            row = session.get(PreferenceInviteLinkRow, key)
            if row is None:
                return None
            if row.expires_at < now:
                return None
            session.expunge(row)
            return row

    def get_or_create_for_instructor(
        self,
        instructor_id: str,
        *,
        created_by: str,
    ) -> PreferenceInviteLinkRow:
        now = utcnow()
        with self._session() as session:
            existing = session.scalar(
                select(PreferenceInviteLinkRow)
                .where(PreferenceInviteLinkRow.instructor_id == instructor_id)
                .where(PreferenceInviteLinkRow.expires_at >= now)
                .order_by(PreferenceInviteLinkRow.created_at.desc())
                .limit(1)
            )
            if existing is not None:
                session.expunge(existing)
                return existing

            key = secrets.token_urlsafe(INVITE_KEY_BYTES)
            row = PreferenceInviteLinkRow(
                key=key,
                instructor_id=instructor_id,
                expires_at=now + INVITE_TTL,
                created_at=now,
                created_by=created_by,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row


preference_invite_repository = PreferenceInviteRepository()
