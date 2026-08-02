import datetime as dtm
from typing import Literal

from beanie import PydanticObjectId

from src.common_pydantic import BaseSchema

Role = Literal["writer", "reader"]
FileType = Literal["spreadsheet", "document"]


class JoinFileRequest(BaseSchema):
    gmail: str
    "Gmail address to add to the file"


class ServiceAccountEmailResponse(BaseSchema):
    email: str
    "Service account email address"


class CreateFileRequest(BaseSchema):
    file_type: FileType
    "Type of file to create (spreadsheet or document)"
    title: str
    "Title of the file"
    default_role: Role
    "Default role for users (writer or reader)"
    owner_gmail: str
    "File owner's Gmail address"


class CreateFileResponse(BaseSchema):
    file_id: str
    "Google File ID"
    file_type: FileType
    "Type of file (spreadsheet or document)"
    title: str
    "Title of the file"
    default_role: Role
    "Default role for users (writer or reader)"
    join_link: str
    "Join link for users"


class CopyFileRequest(BaseSchema):
    file_id: str
    "Existing Google File ID to copy"
    default_role: Role
    "Default role for future respondents (writer or reader)"
    owner_gmail: str
    "File owner's Gmail address"


class CopyFileResponse(BaseSchema):
    file_id: str
    "New Google File ID (copy)"
    file_type: FileType
    "Type of file (spreadsheet or document)"
    title: str
    "Title of the file"
    default_role: Role
    "Default role for users (writer or reader)"
    join_link: str
    "Join link for users"


class GoogleFileSSOJoinInfo(BaseSchema):
    user_id: PydanticObjectId
    "User ID"
    gmail: str
    "Gmail address"
    innomail: str
    "Innopolis email"
    role: Role
    "Role assigned to the user (writer or reader)"
    joined_at: dtm.datetime
    "Date and time when user joined"


class GoogleFileSSOBanInfo(BaseSchema):
    user_id: PydanticObjectId
    "User ID"
    gmail: str
    "Gmail address"
    innomail: str
    "Innopolis email"
    banned_at: dtm.datetime
    "Date and time when user was banned"


class GoogleFile(BaseSchema):
    author_id: PydanticObjectId
    "Author ID"
    default_role: Role
    "Default role for users (writer or reader)"
    slug: str
    "Unique slug for the link"
    file_id: str
    "Google File ID"
    file_type: FileType
    "Type of file (spreadsheet or document)"
    title: str
    "File title"
    owner_gmail: str
    "File owner's Gmail address"
    owner_permission_id: str
    "File owner's permission ID"
    expire_at: dtm.datetime | None = None
    "Expiration date"
    sso_joins: list[GoogleFileSSOJoinInfo] | None = None
    "List of users who joined via SSO"
    sso_joins_count: int
    "Count of SSO joins"
    sso_banned: list[GoogleFileSSOBanInfo] | None = None
    "List of banned users"
    sso_banned_count: int
    "Count of banned users"
    created_at: dtm.datetime
    "Date and time when file was created"


class JoinFileResponse(BaseSchema):
    message: str
    "Message"
    file_id: str
    "Google File ID"


class BanUserRequest(BaseSchema):
    user_id: PydanticObjectId
    "User ID to ban"


class BanUserResponse(BaseSchema):
    message: str
    "Message"


class CleanupResponse(BaseSchema):
    removed: int
    "Number of permissions removed"


class DeleteFileResponse(BaseSchema):
    message: str
    "Message"


class UpdateFileRequest(BaseSchema):
    title: str
    "New title for the file"


class UpdateFileResponse(BaseSchema):
    file_id: str
    "Google File ID"
    title: str
    "Updated title"
    message: str
    "Success message"


class UnbanUserResponse(BaseSchema):
    message: str
    "Message"


class HealthCheckResponse(BaseSchema):
    status: str
    "Health status"
    service: str
    "Service name"


class UpdateUserRoleRequest(BaseSchema):
    role: Role
    "New role for the user (writer or reader)"


class UpdateUserRoleResponse(BaseSchema):
    message: str
    "Success message"


class UpdateDefaultRoleRequest(BaseSchema):
    role: Role
    "New default role for users (writer or reader)"


class UpdateDefaultRoleResponse(BaseSchema):
    message: str
    "Success message"
