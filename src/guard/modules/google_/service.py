import json
from functools import lru_cache

from beanie import PydanticObjectId
from fastapi import HTTPException
from google.oauth2.service_account import Credentials as SaCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.guard.config import settings
from src.guard.modules.google_.constants import FileTypes, HTTPStatuses
from src.logging_ import logger

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]


@lru_cache(maxsize=1)
def get_sa_creds():
    creds = SaCredentials.from_service_account_info(
        json.loads(settings.google.service_account_file_path.read_text()), scopes=SCOPES
    )
    if settings.google.subject:
        creds = creds.with_subject(settings.google.subject)
    return creds


@lru_cache(maxsize=1)
def sheets_service():
    return build("sheets", "v4", credentials=get_sa_creds(), cache_discovery=False)


@lru_cache(maxsize=1)
def drive_service():
    return build("drive", "v3", credentials=get_sa_creds(), cache_discovery=False)


@lru_cache(maxsize=1)
def docs_service():
    return build("docs", "v1", credentials=get_sa_creds(), cache_discovery=False)


def service_email() -> str:
    """Return service account email from credentials."""
    try:
        return settings.google.subject or get_sa_creds().service_account_email
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to get service account email: {e}")
        return "unknown"


def _disable_writers_can_share(file_id: str) -> None:
    drive = drive_service()
    drive.files().update(fileId=file_id, body={"writersCanShare": False}).execute()


def create_spreadsheet(title: str) -> str:
    # Создаём файл как Gmail-владелец через Drive API,
    # так он точно будет жить в диске пользователя
    drive = drive_service()
    body: dict[str, object] = {
        "name": title,
        "mimeType": "application/vnd.google-apps.spreadsheet",
    }
    # если настроена папка — сохраняем в неё
    if settings.google.drive_folder_id:
        body["parents"] = [settings.google.drive_folder_id]
    file = drive.files().create(body=body, fields="id").execute()
    file_id = file["id"]

    _disable_writers_can_share(file_id)

    logger.info(f"Created spreadsheet {file_id} with title '{title}'")
    return file_id


def create_document(title: str) -> str:
    raise HTTPException(status_code=HTTPStatuses.NOT_IMPLEMENTED, detail="Document creation is not implemented yet")


def create_google_file(file_type: str, title: str) -> str:
    if file_type == FileTypes.SPREADSHEET:
        return create_spreadsheet(title)
    elif file_type == FileTypes.DOCUMENT:
        return create_document(title)
    else:
        raise ValueError(f"Unknown file type: {file_type}")


def verify_service_account_access(file_id: str) -> bool:
    """Check if service account has access to the file."""
    try:
        drive = drive_service()
        drive.files().get(fileId=file_id, fields="id").execute()
        return True
    except HttpError as e:
        if e.resp.status in {403, 404}:
            return False
        raise


def copy_google_file(file_id: str) -> tuple[str, str, str]:
    """Copy a Google file and return (new_file_id, title, mime_type)."""
    drive = drive_service()

    if not verify_service_account_access(file_id):
        raise HTTPException(
            status_code=403,
            detail=f"Service account does not have access to file {file_id}. "
            "Please share the file with the service account first.",
        )

    meta = drive.files().get(fileId=file_id, fields="name, mimeType").execute()
    title = meta.get("name", "Untitled")
    mime_type = meta.get("mimeType", "")

    body = {"name": title}
    if settings.google.drive_folder_id:
        body["parents"] = [settings.google.drive_folder_id]

    copied_file = drive.files().copy(fileId=file_id, body=body, fields="id").execute()
    new_file_id = copied_file["id"]

    _disable_writers_can_share(new_file_id)

    logger.info(f"Copied file {file_id} to {new_file_id} with title '{title} (Copy)'")
    return new_file_id, title, mime_type


def verify_file_ownership(file, user_id: str) -> None:
    if str(file.author_id) != user_id:
        raise HTTPException(status_code=HTTPStatuses.FORBIDDEN, detail="You are not the author of this file")


def delete_google_file(file_id: str) -> bool:
    try:
        drive = drive_service()
        drive.files().delete(fileId=file_id).execute()
        logger.info(f"Deleted Google file {file_id}")
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error deleting file {file_id}: {e}")
        return False


def update_file_title(file_id: str, title: str) -> None:
    """Update the title of a Google Drive file."""
    try:
        drive = drive_service()
        drive.files().update(fileId=file_id, body={"name": title}).execute()
        logger.info(f"Updated file {file_id} title to '{title}'")
    except Exception as e:
        logger.error(f"Error updating file {file_id} title: {e}")
        raise


def revoke_file_permission(file_id: str, permission_id: str) -> bool:
    try:
        drive = drive_service()
        drive.permissions().delete(fileId=file_id, permissionId=permission_id).execute()
        logger.info(f"Removed Google Drive permission {permission_id}")
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error removing permission {permission_id}: {e}")
        return False


def accept_ownership_if_pending(file_id: str) -> bool:
    drive = drive_service()
    perms = drive.permissions().list(fileId=file_id, fields="permissions(id,emailAddress,role,pendingOwner)").execute()
    for p in perms.get("permissions", []):
        if p.get("pendingOwner"):
            try:
                drive.permissions().update(
                    fileId=file_id,
                    permissionId=p["id"],
                    body={"role": "owner"},
                    transferOwnership=True,
                ).execute()
                logger.info(f"Accepted ownership transfer for {file_id}")
                return True
            except Exception as e:
                logger.error(f"Error accepting ownership for {file_id}: {e}")
                raise
    return False


def remove_public_links_and_lock_sharing(file_id: str) -> int:
    """Remove anyone/anyoneWithLink permissions and disable writersCanShare. Returns removed count."""
    drive = drive_service()
    removed = 0
    perms = drive.permissions().list(fileId=file_id, fields="permissions(id,type,role)").execute()
    for p in perms.get("permissions", []):
        if p.get("type") in {"anyone", "domain"}:
            try:
                drive.permissions().delete(fileId=file_id, permissionId=p["id"]).execute()
                removed += 1
            except Exception as e:  # noqa: BLE001
                logger.error(f"Error removing public permission {p['id']} on {file_id}: {e}")
    _disable_writers_can_share(file_id)
    return removed


def count_user_permissions(file_id: str) -> int:
    drive = drive_service()
    perms = drive.permissions().list(fileId=file_id, fields="permissions(id,type)").execute()
    return sum(1 for p in perms.get("permissions", []) if p.get("type") == "user")


def update_user_permission(file_id: str, permission_id: str, role: str) -> None:
    """Update a user's permission role in Google Drive."""
    try:
        drive = drive_service()
        drive.permissions().update(
            fileId=file_id,
            permissionId=permission_id,
            body={"role": role},
        ).execute()
        logger.info(f"Updated permission {permission_id} to role {role} for file {file_id}")
    except Exception as e:
        logger.error(f"Error updating permission {permission_id} for file {file_id}: {e}")
        raise


def update_all_user_permissions(file_id: str, role: str, joins: list) -> int:
    """Update all user permissions in Google Drive. Returns number of updated permissions."""
    updated = 0
    drive = drive_service()

    for join in joins:
        if join.permission_id:
            try:
                drive.permissions().update(
                    fileId=file_id,
                    permissionId=join.permission_id,
                    body={"role": role},
                ).execute()
                updated += 1
                logger.info(f"Updated permission {join.permission_id} to role {role} for file {file_id}")
            except Exception as e:  # noqa: BLE001
                logger.error(f"Error updating permission {join.permission_id} for file {file_id}: {e}")

    return updated


def get_user_id_from_token(user_token_data) -> PydanticObjectId:
    return PydanticObjectId(user_token_data.innohassle_id)


def generate_join_link(slug: str) -> str:
    return f"{settings.base_url}/guard/google/files/{slug}/join"


def grant_owner_permission(file_id: str, owner_gmail: str) -> str:
    """Grant write permission to the file owner and return permission_id."""
    from src.guard.modules.google_.exceptions import InvalidGmailException, UnknownErrorException

    drive = drive_service()

    try:
        permission = (
            drive.permissions()
            .create(
                fileId=file_id,
                body={"type": "user", "role": "writer", "emailAddress": owner_gmail},
                sendNotificationEmail=False,
            )
            .execute()
        )
    except HttpError as e:
        if e.resp.status == 400 and ("invalidSharingRequest" in str(e) or "permission.emailAddress" in str(e)):
            raise InvalidGmailException(gmail=owner_gmail)
        raise UnknownErrorException()

    permission_id = permission.get("id")
    logger.info(
        f"Successfully granted owner permission to {owner_gmail} for file {file_id}, permission_id={permission_id}"
    )

    return permission_id


# def determine_user_role(file, user_id: PydanticObjectId, requested_role: str) -> str:
#     if str(file.author_id) == str(user_id):
#         return UserRoles.WRITER
#     return requested_role


async def add_user_to_file(file_slug: str, user_id: PydanticObjectId, gmail: str, innomail: str):
    from src.guard.modules.google_.exceptions import (
        FileNotFoundException,
        GmailAlreadyUsedException,
        InvalidGmailException,
        UnknownErrorException,
    )
    from src.guard.modules.google_.repository import google_file_repository

    file = await google_file_repository.get_by_slug(file_slug)
    if not file:
        raise FileNotFoundException(slug=file_slug)

    role = file.default_role

    # if user is the owner of the file, we don't need to add him again
    if str(file.author_id) == str(user_id):
        logger.info(f"User {user_id} is the owner of the file {file_slug}, no need to add him again")
        return file
    # if user already joined the file with the same gmail, we don't need to add him again
    if any(join.gmail == gmail and str(join.user_id) == str(user_id) for join in file.sso_joins):
        logger.info(f"User {user_id} already joined the file {file_slug} with the same gmail, no need to add him again")
        return file
    # if user already joined the file, but with a different gmail, we need to revoke his permission and add him again with the same role then
    elif any(join.gmail != gmail and str(join.user_id) == str(user_id) for join in file.sso_joins):
        logger.info(
            f"User {user_id} already joined the file {file_slug} with a different gmail, revoking permission and adding again"
        )
        join = next(join for join in file.sso_joins if join.gmail != gmail and str(join.user_id) == str(user_id))
        drive = drive_service()

        try:
            permission = (
                drive.permissions()
                .create(
                    fileId=file.file_id,
                    body={"type": "user", "role": join.role, "emailAddress": gmail},
                    sendNotificationEmail=False,
                )
                .execute()
            )
            if join.permission_id:
                revoke_file_permission(file.file_id, join.permission_id)
            await google_file_repository.remove_user_from_file(slug=file_slug, user_id=user_id)

            await google_file_repository.join_user_to_file(
                slug=file_slug,
                user_id=user_id,
                gmail=gmail,
                innomail=innomail,
                role=join.role,
                permission_id=permission.get("id"),
            )

            logger.info(f"Successfully added {gmail} as {join.role} to file {file.file_id}")

            return file
        except HttpError as e:
            if e.resp.status == 400 and ("invalidSharingRequest" in str(e) or "permission.emailAddress" in str(e)):
                raise InvalidGmailException(gmail=gmail)
            raise UnknownErrorException()

    # if user joined with gmail that some other user uses, we raise an error
    elif any(join.gmail == gmail and str(join.user_id) != str(user_id) for join in file.sso_joins):
        logger.info(
            f"User {user_id} joined the file {file_slug} with gmail {gmail} that some other user uses, raising an error"
        )
        raise GmailAlreadyUsedException(gmail=gmail)
    else:
        logger.info(f"User {user_id} is not joined the file {file_slug}, adding him with role {role}")

        drive = drive_service()

        try:
            permission = (
                drive.permissions()
                .create(
                    fileId=file.file_id,
                    body={"type": "user", "role": role, "emailAddress": gmail},
                    sendNotificationEmail=False,
                )
                .execute()
            )
        except HttpError as e:
            if e.resp.status == 400 and ("invalidSharingRequest" in str(e) or "permission.emailAddress" in str(e)):
                raise InvalidGmailException(gmail=gmail)
            raise UnknownErrorException()

        permission_id = permission.get("id")

        await google_file_repository.join_user_to_file(
            slug=file_slug,
            user_id=user_id,
            gmail=gmail,
            innomail=innomail,
            role=role,
            permission_id=permission_id,
        )

        logger.info(f"Successfully added {gmail} as {role} to file {file.file_id}")

        return file
