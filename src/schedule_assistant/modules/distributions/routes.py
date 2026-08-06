import json
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import Response as FastAPIResponse

from src.schedule_assistant.dependencies import ModeratorDep, VerifyTokenDep
from src.schedule_assistant.modules.distributions.mapping import (
    section_target_groups,
    sort_labels_by_suggested_mapping,
    suggest_mapping,
)
from src.schedule_assistant.modules.distributions.parser import normalize_email, parse_distribution_xlsx
from src.schedule_assistant.modules.distributions.repository import (
    DistributionUploadRecord,
    distribution_upload_repository,
)
from src.schedule_assistant.modules.distributions.schemas import (
    DistributionApplyResponse,
    DistributionApplyResultItem,
    DistributionLabelStat,
    DistributionPreviewResponse,
    DistributionPreviewStats,
    DistributionTargetGroup,
    DistributionUploadDetail,
    DistributionUploadStats,
    DistributionUploadSummary,
)
from src.schedule_assistant.modules.schedule_config.repository import schedule_config_repository
from src.schedule_assistant.modules.schedule_config.schemas import SectionConfig

router = APIRouter(prefix="/distributions", tags=["Distributions"])


def _moderator_email(moderator: ModeratorDep) -> str:
    user, _token = moderator
    return user.email


def _set_revision_etag(response: Response, revision: int) -> None:
    response.headers["ETag"] = f'"{revision}"'


def _parse_json_list(raw: str | None, *, field_name: str) -> list[str] | None:
    if raw is None or not raw.strip():
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON for {field_name}",
        ) from exc
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be a JSON array of strings",
        )
    return value


def _parse_mapping(raw: str) -> dict[str, str | None]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON for mapping",
        ) from exc
    if not isinstance(value, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mapping must be a JSON object",
        )
    mapping: dict[str, str | None] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="mapping keys must be strings",
            )
        if item is not None and not isinstance(item, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="mapping values must be strings or null",
            )
        mapping[key] = item
    return mapping


def _parse_emails_by_label(raw: str | None) -> dict[str, list[str]] | None:
    if raw is None or not raw.strip():
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON for emails_by_label",
        ) from exc
    if not isinstance(value, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="emails_by_label must be a JSON object",
        )
    result: dict[str, list[str]] = {}
    for key, emails in value.items():
        if not isinstance(key, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="emails_by_label keys must be strings",
            )
        if not isinstance(emails, list) or not all(isinstance(item, str) for item in emails):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="emails_by_label values must be arrays of strings",
            )
        normalized: list[str] = []
        seen: set[str] = set()
        for email in emails:
            cleaned = normalize_email(email)
            if cleaned is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid email {email!r} for label {key!r}",
                )
            if cleaned in seen:
                continue
            seen.add(cleaned)
            normalized.append(cleaned)
        result[key] = normalized
    return result


def _get_section(section_code: str) -> SectionConfig:
    sections = schedule_config_repository.get_sections().sections
    for section in sections:
        if section.code == section_code:
            return section
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Section not found: {section_code!r}",
    )


async def _read_upload(file: UploadFile) -> bytes:
    filename = (file.filename or "").lower()
    if filename and not filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an Excel .xlsx workbook",
        )
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    return raw


def _stats_from_dict(raw: dict[str, Any]) -> DistributionUploadStats:
    return DistributionUploadStats(
        row_count=int(raw.get("row_count") or 0),
        email_count=int(raw.get("email_count") or 0),
        label_count=int(raw.get("label_count") or 0),
        mapped_label_count=int(raw.get("mapped_label_count") or 0),
        skipped_label_count=int(raw.get("skipped_label_count") or 0),
        updated_group_count=int(raw.get("updated_group_count") or 0),
    )


def _summary_from_record(record: DistributionUploadRecord) -> DistributionUploadSummary:
    stats = _stats_from_dict(record.stats)
    return DistributionUploadSummary(
        id=record.id,
        section_code=record.section_code,
        filename=record.filename,
        content_type=record.content_type,
        uploaded_by=record.uploaded_by,
        uploaded_at=record.uploaded_at,
        sheet_name=record.sheet_name,
        email_column=record.email_column,
        membership_columns=record.membership_columns,
        stats=stats,
        updated_group_count=len(record.updated_groups),
        skipped_label_count=len(record.skipped_labels),
        revision=record.revision,
        file_size=record.file_size,
    )


def _detail_from_record(record: DistributionUploadRecord) -> DistributionUploadDetail:
    summary = _summary_from_record(record)
    return DistributionUploadDetail(
        **summary.model_dump(),
        mapping=record.mapping,
        updated_groups=[DistributionApplyResultItem.model_validate(item) for item in record.updated_groups],
        skipped_labels=record.skipped_labels,
    )


def _build_preview(
    *,
    section_code: str,
    file_bytes: bytes,
    sheet_name: str | None,
    email_column: str | None,
    membership_columns: list[str] | None,
    forward_fill_columns: list[str] | None,
) -> DistributionPreviewResponse:
    section = _get_section(section_code)
    students_groups = schedule_config_repository.list_student_groups()
    targets = section_target_groups(section, students_groups)

    try:
        parsed = parse_distribution_xlsx(
            file_bytes,
            sheet_name=sheet_name,
            email_column=email_column,
            membership_columns=membership_columns,
            forward_fill_columns=forward_fill_columns,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    excel_labels = [item.label for item in parsed.labels]
    suggested = suggest_mapping(excel_labels, targets)
    unmapped = sum(1 for label in excel_labels if not suggested.get(label))
    ordered_labels = sort_labels_by_suggested_mapping(
        parsed.labels,
        label_of=lambda item: item.label,
        suggested_mapping=suggested,
        target_group_codes=[group.code for group in targets],
    )

    return DistributionPreviewResponse(
        section_code=section_code,
        sheet_names=parsed.sheet_names,
        sheet_name=parsed.sheet_name,
        columns=parsed.columns,
        header_row_index=parsed.header_row_index,
        email_column=parsed.email_column,
        membership_columns=parsed.membership_columns,
        forward_fill_columns=parsed.forward_fill_columns,
        labels=[
            DistributionLabelStat(
                label=item.label,
                email_count=item.email_count,
                emails=parsed.emails_by_label.get(item.label, []),
                suggested_group_code=suggested.get(item.label),
            )
            for item in ordered_labels
        ],
        suggested_mapping=suggested,
        stats=DistributionPreviewStats(
            row_count=parsed.row_count,
            email_count=parsed.email_count,
            label_count=len(parsed.labels),
            unmapped_label_count=unmapped,
        ),
        target_groups=[
            DistributionTargetGroup(
                code=group.code,
                name=group.name,
                kind=group.kind,
                students_count=len(group.students),
            )
            for group in targets
        ],
    )


@router.get("/uploads")
async def list_distribution_uploads(
    _user_and_token: VerifyTokenDep,
    section_code: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[DistributionUploadSummary]:
    records = distribution_upload_repository.list_uploads(section_code=section_code, limit=limit)
    return [_summary_from_record(record) for record in records]


@router.get("/uploads/{upload_id}")
async def get_distribution_upload(
    upload_id: str,
    _user_and_token: VerifyTokenDep,
) -> DistributionUploadDetail:
    record = distribution_upload_repository.get(upload_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Distribution upload not found: {upload_id!r}",
        )
    return _detail_from_record(record)


@router.get("/uploads/{upload_id}/file")
async def download_distribution_upload(
    upload_id: str,
    _user_and_token: VerifyTokenDep,
) -> FastAPIResponse:
    filename, content_type, file_bytes = distribution_upload_repository.get_file(upload_id)
    ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "distribution.xlsx"
    quoted = quote(filename)
    return FastAPIResponse(
        content=file_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quoted}",
        },
    )


@router.post("/preview")
async def preview_distribution(
    moderator: ModeratorDep,
    file: Annotated[UploadFile, File(description="Distribution Excel workbook")],
    section_code: Annotated[str, Form()],
    sheet_name: Annotated[str | None, Form()] = None,
    email_column: Annotated[str | None, Form()] = None,
    membership_columns: Annotated[str | None, Form(description="JSON array of column names")] = None,
    forward_fill_columns: Annotated[str | None, Form(description="JSON array of column names")] = None,
) -> DistributionPreviewResponse:
    _ = moderator
    file_bytes = await _read_upload(file)
    return _build_preview(
        section_code=section_code,
        file_bytes=file_bytes,
        sheet_name=sheet_name or None,
        email_column=email_column or None,
        membership_columns=_parse_json_list(membership_columns, field_name="membership_columns"),
        forward_fill_columns=_parse_json_list(forward_fill_columns, field_name="forward_fill_columns"),
    )


@router.post("/apply")
async def apply_distribution(
    response: Response,
    moderator: ModeratorDep,
    file: Annotated[UploadFile, File(description="Distribution Excel workbook")],
    section_code: Annotated[str, Form()],
    mapping: Annotated[str, Form(description="JSON object excel_label -> group_code|null")],
    sheet_name: Annotated[str | None, Form()] = None,
    email_column: Annotated[str | None, Form()] = None,
    membership_columns: Annotated[str | None, Form(description="JSON array of column names")] = None,
    forward_fill_columns: Annotated[str | None, Form(description="JSON array of column names")] = None,
    emails_by_label: Annotated[
        str | None,
        Form(description="Optional JSON object excel_label -> email[] overrides"),
    ] = None,
) -> DistributionApplyResponse:
    section = _get_section(section_code)
    students_groups = schedule_config_repository.list_student_groups()
    targets = section_target_groups(section, students_groups)
    allowed_codes = {group.code for group in targets}

    file_bytes = await _read_upload(file)
    label_mapping = _parse_mapping(mapping)
    membership_cols = _parse_json_list(membership_columns, field_name="membership_columns")
    forward_fill_cols = _parse_json_list(forward_fill_columns, field_name="forward_fill_columns")
    email_overrides = _parse_emails_by_label(emails_by_label)

    try:
        parsed = parse_distribution_xlsx(
            file_bytes,
            sheet_name=sheet_name or None,
            email_column=email_column or None,
            membership_columns=membership_cols,
            forward_fill_columns=forward_fill_cols,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    emails_by_label_map = dict(parsed.emails_by_label)
    if email_overrides is not None:
        for label, emails in email_overrides.items():
            emails_by_label_map[label] = emails

    updates: dict[str, list[str]] = {}
    updated_items: list[DistributionApplyResultItem] = []
    skipped: list[str] = []

    for label, emails in emails_by_label_map.items():
        target_code = label_mapping.get(label)
        if not target_code:
            skipped.append(label)
            continue
        if target_code not in allowed_codes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mapped group {target_code!r} is not in section {section_code!r}",
            )
        existing = updates.get(target_code, [])
        seen = set(existing)
        merged = list(existing)
        for email in emails:
            if email not in seen:
                seen.add(email)
                merged.append(email)
        updates[target_code] = merged
        updated_items.append(
            DistributionApplyResultItem(
                group_code=target_code,
                excel_label=label,
                students_count=len(emails),
            )
        )

    uploaded_by = _moderator_email(moderator)
    revision = schedule_config_repository.replace_student_group_students(
        updates,
        saved_by=uploaded_by,
    )
    mapped_label_count = sum(1 for label in emails_by_label_map if label_mapping.get(label))
    upload = distribution_upload_repository.create(
        section_code=section_code,
        filename=file.filename or "distribution.xlsx",
        content_type=file.content_type or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        file_bytes=file_bytes,
        uploaded_by=uploaded_by,
        sheet_name=parsed.sheet_name,
        email_column=parsed.email_column,
        membership_columns=parsed.membership_columns,
        mapping=label_mapping,
        stats={
            "row_count": parsed.row_count,
            "email_count": sum(len(emails) for emails in emails_by_label_map.values()),
            "label_count": len(emails_by_label_map),
            "mapped_label_count": mapped_label_count,
            "skipped_label_count": len(skipped),
            "updated_group_count": len(updates),
        },
        updated_groups=[item.model_dump() for item in updated_items],
        skipped_labels=skipped,
        revision=revision,
    )
    _set_revision_etag(response, revision)
    return DistributionApplyResponse(
        section_code=section_code,
        updated_groups=updated_items,
        skipped_labels=skipped,
        revision=revision,
        upload_id=upload.id,
    )
