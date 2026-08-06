from pydantic import BaseModel, Field


class DistributionLabelStat(BaseModel):
    label: str
    email_count: int
    emails: list[str] = Field(default_factory=list)
    suggested_group_code: str | None = None


class DistributionPreviewStats(BaseModel):
    row_count: int
    email_count: int
    label_count: int
    unmapped_label_count: int


class DistributionTargetGroup(BaseModel):
    code: str
    name: str | None = None
    kind: str
    students_count: int = 0


class DistributionPreviewResponse(BaseModel):
    section_code: str
    sheet_names: list[str]
    sheet_name: str
    columns: list[str]
    header_row_index: int
    email_column: str | None
    membership_columns: list[str]
    forward_fill_columns: list[str]
    labels: list[DistributionLabelStat]
    suggested_mapping: dict[str, str | None]
    stats: DistributionPreviewStats
    target_groups: list[DistributionTargetGroup]


class DistributionApplyResultItem(BaseModel):
    group_code: str
    excel_label: str
    students_count: int


class DistributionApplyResponse(BaseModel):
    section_code: str
    updated_groups: list[DistributionApplyResultItem] = Field(default_factory=list)
    skipped_labels: list[str] = Field(default_factory=list)
    revision: int
    upload_id: str | None = None


class DistributionUploadStats(BaseModel):
    row_count: int = 0
    email_count: int = 0
    label_count: int = 0
    mapped_label_count: int = 0
    skipped_label_count: int = 0
    updated_group_count: int = 0


class DistributionUploadSummary(BaseModel):
    id: str
    section_code: str
    filename: str
    content_type: str
    uploaded_by: str
    uploaded_at: str
    sheet_name: str | None = None
    email_column: str | None = None
    membership_columns: list[str] = Field(default_factory=list)
    stats: DistributionUploadStats = Field(default_factory=DistributionUploadStats)
    updated_group_count: int = 0
    skipped_label_count: int = 0
    revision: int = 0
    file_size: int = 0


class DistributionUploadDetail(DistributionUploadSummary):
    mapping: dict[str, str | None] = Field(default_factory=dict)
    updated_groups: list[DistributionApplyResultItem] = Field(default_factory=list)
    skipped_labels: list[str] = Field(default_factory=list)
