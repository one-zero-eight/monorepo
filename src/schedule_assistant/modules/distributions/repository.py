import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.schedule_assistant.models import DistributionUploadRow
from src.schedule_assistant.utcnow import utcnow


@dataclass
class DistributionUploadRecord:
    id: str
    section_code: str
    filename: str
    content_type: str
    uploaded_by: str
    uploaded_at: str
    sheet_name: str | None
    email_column: str | None
    membership_columns: list[str]
    mapping: dict[str, str | None]
    stats: dict[str, Any]
    updated_groups: list[dict[str, Any]]
    skipped_labels: list[str]
    revision: int
    file_size: int


def _row_to_record(row: DistributionUploadRow) -> DistributionUploadRecord:
    return DistributionUploadRecord(
        id=row.id,
        section_code=row.section_code,
        filename=row.filename,
        content_type=row.content_type,
        uploaded_by=row.uploaded_by,
        uploaded_at=row.uploaded_at.isoformat(),
        sheet_name=row.sheet_name,
        email_column=row.email_column,
        membership_columns=list(row.membership_columns or []),
        mapping=dict(row.mapping or {}),
        stats=dict(row.stats or {}),
        updated_groups=list(row.updated_groups or []),
        skipped_labels=list(row.skipped_labels or []),
        revision=row.revision,
        file_size=len(row.file_bytes or b""),
    )


class DistributionUploadRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        section_code: str,
        filename: str,
        content_type: str,
        file_bytes: bytes,
        uploaded_by: str,
        sheet_name: str | None,
        email_column: str | None,
        membership_columns: list[str],
        mapping: dict[str, str | None],
        stats: dict[str, Any],
        updated_groups: list[dict[str, Any]],
        skipped_labels: list[str],
        revision: int,
    ) -> DistributionUploadRecord:
        upload_id = str(uuid.uuid4())
        row = DistributionUploadRow(
            id=upload_id,
            section_code=section_code,
            filename=filename,
            content_type=content_type or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            file_bytes=file_bytes,
            uploaded_by=uploaded_by,
            uploaded_at=utcnow(),
            sheet_name=sheet_name,
            email_column=email_column,
            membership_columns=membership_columns,
            mapping=mapping,
            stats=stats,
            updated_groups=updated_groups,
            skipped_labels=skipped_labels,
            revision=revision,
        )
        self.session.add(row)
        self.session.flush()
        self.session.refresh(row)
        return _row_to_record(row)

    def list_uploads(self, *, section_code: str | None = None, limit: int = 50) -> list[DistributionUploadRecord]:
        stmt = select(DistributionUploadRow).order_by(DistributionUploadRow.uploaded_at.desc()).limit(limit)
        if section_code:
            stmt = stmt.where(DistributionUploadRow.section_code == section_code)
        rows = self.session.scalars(stmt).all()
        return [_row_to_record(row) for row in rows]

    def get(self, upload_id: str) -> DistributionUploadRecord | None:
        row = self.session.get(DistributionUploadRow, upload_id)
        if row is None:
            return None
        return _row_to_record(row)

    def get_file(self, upload_id: str) -> tuple[str, str, bytes]:
        row = self.session.get(DistributionUploadRow, upload_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Distribution upload not found: {upload_id!r}",
            )
        return row.filename, row.content_type, row.file_bytes
