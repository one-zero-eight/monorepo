import datetime as dtm
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.schedule_assistant.models import PreferenceInviteLinkRow
from src.schedule_assistant.utcnow import utcnow

INVITE_KEY_BYTES = 8
INVITE_TTL = dtm.timedelta(days=30)


class PreferenceInviteRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_active_by_key(self, key: str) -> PreferenceInviteLinkRow | None:
        now = utcnow()
        row = self.session.get(PreferenceInviteLinkRow, key)
        if row is None:
            return None
        if row.expires_at < now:
            return None
        self.session.expunge(row)
        return row

    def get_or_create_for_instructor(
        self,
        instructor_id: str,
        *,
        created_by: str,
    ) -> PreferenceInviteLinkRow:
        now = utcnow()
        existing = self.session.scalar(
            select(PreferenceInviteLinkRow)
            .where(PreferenceInviteLinkRow.instructor_id == instructor_id)
            .where(PreferenceInviteLinkRow.expires_at >= now)
            .order_by(PreferenceInviteLinkRow.created_at.desc())
            .limit(1)
        )
        if existing is not None:
            self.session.expunge(existing)
            return existing

        key = secrets.token_urlsafe(INVITE_KEY_BYTES)
        row = PreferenceInviteLinkRow(
            key=key,
            instructor_id=instructor_id,
            expires_at=now + INVITE_TTL,
            created_at=now,
            created_by=created_by,
        )
        self.session.add(row)
        self.session.flush()
        self.session.refresh(row)
        self.session.expunge(row)
        return row
