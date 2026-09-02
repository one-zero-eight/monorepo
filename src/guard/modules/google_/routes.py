from beanie import PydanticObjectId
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from googleapiclient.errors import HttpError

from src.dependencies import INH_TOKEN_AUTH
from src.guard.modules.google_.exceptions import (
    FileNotFoundException,
    GmailAlreadyUsedException,
    InvalidGmailException,
    UserBannedException,
)
from src.guard.modules.google_.greeting import setup_greeting_sheet
from src.guard.modules.google_.repository import google_file_repository
from src.guard.modules.google_.schemas import (
    BanUserRequest,
    BanUserResponse,
    CleanupResponse,
    CopyFileRequest,
    CopyFileResponse,
    CreateFileRequest,
    CreateFileResponse,
    DeleteFileResponse,
    GoogleFile,
    GoogleFileSSOBanInfo,
    GoogleFileSSOJoinInfo,
    HealthCheckResponse,
    JoinFileRequest,
    JoinFileResponse,
    ServiceAccountEmailResponse,
    UnbanUserResponse,
    UpdateDefaultRoleRequest,
    UpdateDefaultRoleResponse,
    UpdateFileRequest,
    UpdateFileResponse,
    UpdateUserRoleRequest,
    UpdateUserRoleResponse,
)
from src.guard.modules.google_.service import (
    add_user_to_file,
    copy_google_file,
    create_google_file,
    delete_google_file,
    generate_join_link,
    get_user_id_from_token,
    grant_owner_permission,
    revoke_file_permission,
    service_email,
    sheets_service,
    update_all_user_permissions,
    update_file_title,
    update_user_permission,
    verify_file_ownership,
)
from src.logging_ import logger

router = APIRouter(prefix="/google", tags=["Google"], route_class=AutoDeriveResponsesAPIRoute)


@router.get("/health")
async def health_check() -> HealthCheckResponse:
    """Health check endpoint to verify service is running."""
    try:
        service_email()
        return HealthCheckResponse(status="healthy", service="google")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Health check failed | error={e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@router.get("/service-account-email")
def get_service_account_email() -> ServiceAccountEmailResponse:
    """Get the service account email address."""
    try:
        email = service_email()
        return ServiceAccountEmailResponse(email=email)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Service account not configured: {e}")


@router.post("/files")
async def create_file(
    request: CreateFileRequest,
    user_token_data: INH_TOKEN_AUTH,
    background_tasks: BackgroundTasks,
) -> CreateFileResponse:
    """Create a new Google file (spreadsheet or document) and return join link."""
    file_id = None

    try:
        logger.info(
            f"Creating file | user_id={user_token_data.innohassle_id} "
            f"email={user_token_data.email} type={request.file_type} "
            f"title='{request.title}' role={request.default_role} "
            f"owner_gmail={request.owner_gmail}"
        )

        file_id = create_google_file(file_type=request.file_type, title=request.title)

        # Grant owner permission
        owner_permission_id = grant_owner_permission(file_id, request.owner_gmail)

        file = await google_file_repository.create_file(
            author_id=get_user_id_from_token(user_token_data),
            default_role=request.default_role,
            file_id=file_id,
            file_type=request.file_type,
            title=request.title,
            owner_gmail=request.owner_gmail,
            owner_permission_id=owner_permission_id,
        )

        join_link = generate_join_link(file.slug)

        if request.file_type == "spreadsheet":
            background_tasks.add_task(
                setup_greeting_sheet,
                sheets_service=sheets_service(),
                spreadsheet_id=file_id,
                join_link=join_link,
                respondent_role=request.default_role,
            )

        return CreateFileResponse(
            file_id=file_id,
            file_type=request.file_type,
            title=request.title,
            default_role=request.default_role,
            join_link=join_link,
        )
    except HttpError as e:
        if file_id:
            delete_google_file(file_id)
        logger.error(f"Google API error: {e}")
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:  # noqa: BLE001
        if file_id:
            delete_google_file(file_id)
        logger.error(f"Create file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/copy")
async def copy_file(
    request: CopyFileRequest,
    user_token_data: INH_TOKEN_AUTH,
) -> CopyFileResponse:
    """Copy an existing Google file to service account's drive and add it to the system."""
    try:
        logger.info(
            f"Copying file | user_id={user_token_data.innohassle_id} "
            f"source_file_id={request.file_id} default_role={request.default_role} "
            f"owner_gmail={request.owner_gmail}"
        )

        new_file_id, title, mime_type = copy_google_file(request.file_id)

        if "spreadsheet" in mime_type:
            file_type = "spreadsheet"
        elif "document" in mime_type:
            file_type = "document"
        else:
            delete_google_file(new_file_id)
            raise HTTPException(status_code=400, detail=f"Unsupported mimeType: {mime_type}")

        # Grant owner permission
        owner_permission_id = grant_owner_permission(new_file_id, request.owner_gmail)

        file = await google_file_repository.create_file(
            author_id=get_user_id_from_token(user_token_data),
            default_role=request.default_role,
            file_id=new_file_id,
            file_type=file_type,  # type: ignore[arg-type]
            title=f"{title} (Copy)",
            owner_gmail=request.owner_gmail,
            owner_permission_id=owner_permission_id,
        )

        join_link = generate_join_link(file.slug)

        logger.info(
            f"File copied successfully | user_id={user_token_data.innohassle_id} "
            f"source_file_id={request.file_id} new_file_id={new_file_id}"
        )

        return CopyFileResponse(
            file_id=new_file_id,
            file_type=file_type,  # type: ignore[arg-type]
            title=f"{title} (Copy)",
            default_role=request.default_role,
            join_link=join_link,
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"Copy file error | source_file_id={request.file_id} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files/{slug}")
async def delete_file(
    slug: str,
    user_token_data: INH_TOKEN_AUTH,
) -> DeleteFileResponse:
    """Delete a file by slug (author only)."""
    try:
        file = await google_file_repository.get_by_slug(slug)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        verify_file_ownership(file, user_token_data.innohassle_id)

        deleted = await google_file_repository.delete_by_slug(slug)
        if not deleted:
            raise HTTPException(status_code=404, detail="File not found")
        return DeleteFileResponse(message="File deleted")
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error deleting file | slug={slug} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/files/{slug}")
async def update_file(
    slug: str,
    request: UpdateFileRequest,
    user_token_data: INH_TOKEN_AUTH,
) -> UpdateFileResponse:
    """Update file title (author only)."""
    try:
        file = await google_file_repository.get_by_slug(slug)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        verify_file_ownership(file, user_token_data.innohassle_id)

        logger.info(
            f"Updating file title | user_id={user_token_data.innohassle_id} "
            f"slug={slug} old_title='{file.title}' new_title='{request.title}'"
        )

        update_file_title(file.file_id, request.title)

        updated_file = await google_file_repository.update_file_title(slug, request.title)
        if not updated_file:
            raise HTTPException(status_code=404, detail="File not found")

        logger.info(f"File title updated | slug={slug} title='{request.title}'")

        return UpdateFileResponse(
            file_id=file.file_id,
            title=request.title,
            message="File title updated successfully",
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error updating file | slug={slug} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files")
async def get_files(
    user_token_data: INH_TOKEN_AUTH,
) -> list[GoogleFile]:
    """Get all files for the user (brief info without joins and banned)."""
    try:
        files = await google_file_repository.get_by_author_id(user_token_data.innohassle_id)
        result: list[GoogleFile] = []
        for file in files:
            if file.id is None:
                raise RuntimeError("Stored Google file is missing its document ID")
            result.append(
                GoogleFile(
                    author_id=file.author_id,
                    default_role=file.default_role,
                    slug=file.slug,
                    file_id=file.file_id,
                    file_type=file.file_type,
                    owner_gmail=file.owner_gmail,
                    owner_permission_id=file.owner_permission_id,
                    title=file.title,
                    expire_at=file.expire_at,
                    sso_joins_count=len(file.sso_joins or []),
                    sso_banned_count=len(file.sso_banned or []),
                    created_at=file.id.generation_time,
                )
            )
        return result
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error getting files | user_id={user_token_data.innohassle_id} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/{slug}")
async def get_file(
    slug: str,
    user_token_data: INH_TOKEN_AUTH,
) -> GoogleFile:
    """Get full file information including joins and banned users."""
    try:
        file = await google_file_repository.get_by_slug(slug)

        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        verify_file_ownership(file, user_token_data.innohassle_id)
        if file.id is None:
            raise RuntimeError("Stored Google file is missing its document ID")

        return GoogleFile(
            author_id=file.author_id,
            default_role=file.default_role,
            slug=file.slug,
            file_id=file.file_id,
            file_type=file.file_type,
            title=file.title,
            owner_gmail=file.owner_gmail,
            owner_permission_id=file.owner_permission_id,
            expire_at=file.expire_at,
            sso_joins=[
                GoogleFileSSOJoinInfo(
                    user_id=join.user_id,
                    gmail=join.gmail,
                    innomail=join.innomail,
                    role=join.role,
                    joined_at=join.joined_at,
                )
                for join in file.sso_joins
            ],
            sso_banned=[
                GoogleFileSSOBanInfo(
                    user_id=ban.user_id,
                    gmail=ban.gmail,
                    innomail=ban.innomail,
                    banned_at=ban.banned_at,
                )
                for ban in file.sso_banned
            ],
            sso_joins_count=len(file.sso_joins or []),
            sso_banned_count=len(file.sso_banned or []),
            created_at=file.id.generation_time,
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error getting file | slug={slug} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/{slug}/joins")
async def join_file(
    slug: str,
    request: JoinFileRequest,
    user_token_data: INH_TOKEN_AUTH,
) -> JoinFileResponse:
    """Add user to the file with specified role."""

    try:
        logger.info(
            f"Joining file | user_id={user_token_data.innohassle_id} "
            f"innomail={user_token_data.email} gmail={request.gmail} slug={slug}"
        )

        file = await add_user_to_file(
            file_slug=slug,
            user_id=get_user_id_from_token(user_token_data),
            gmail=request.gmail,
            innomail=user_token_data.email,
        )

        logger.info(
            f"File joined successfully | user_id={user_token_data.innohassle_id} "
            f"gmail={request.gmail} file_id={file.file_id}"
        )

        return JoinFileResponse(
            message=f"Successfully added {request.gmail}",
            file_id=file.file_id,
        )

    except HttpError as e:
        logger.error(
            f"Google API error | user_id={user_token_data.innohassle_id} gmail={request.gmail} slug={slug} error={e}"
        )
        if e.resp.status == 403:
            raise HTTPException(
                status_code=403,
                detail="Permission denied. Make sure the service account has access to the file.",
            )
        if e.resp.status == 404:
            raise HTTPException(status_code=404, detail="File not found.")
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except UserBannedException as e:
        logger.error(f"User banned: {e}")
        raise HTTPException(status_code=403, detail="Permission denied. You are banned from this file.")
    except InvalidGmailException as e:
        logger.error(f"Invalid gmail: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Gmail {e.gmail} does not exist or is not associated with a Google account",
        )
    except FileNotFoundException as e:
        logger.error(f"File not found: {e}")
        raise HTTPException(status_code=404, detail=f"File with slug {e.slug} not found")
    except GmailAlreadyUsedException as e:
        logger.error(f"Gmail already used: {e}")
        raise HTTPException(status_code=400, detail=f"Gmail {e.gmail} is already used by another user")
    except Exception as e:  # noqa: BLE001
        logger.error(
            f"Error joining file | user_id={user_token_data.innohassle_id} gmail={request.gmail} slug={slug} error={e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/{slug}/bans")
async def ban_user(
    slug: str,
    request: BanUserRequest,
    user_token_data: INH_TOKEN_AUTH,
) -> BanUserResponse:
    """Ban user from the file."""

    try:
        file = await google_file_repository.get_by_slug(slug)

        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        verify_file_ownership(file, user_token_data.innohassle_id)

        joins_to_ban = [join for join in file.sso_joins if join.user_id == request.user_id]

        if not joins_to_ban:
            raise HTTPException(status_code=404, detail=f"User with user_id {request.user_id} not found in joins")

        for join_to_ban in joins_to_ban:
            logger.info(
                f"Banning user | author_id={user_token_data.innohassle_id} "
                f"banned_user_id={join_to_ban.user_id} gmail={join_to_ban.gmail} slug={slug}"
            )

            if join_to_ban.permission_id:
                revoke_file_permission(file.file_id, join_to_ban.permission_id)

            await google_file_repository.ban_user_from_file(
                slug=slug,
                user_id=join_to_ban.user_id,
                gmail=join_to_ban.gmail,
                innomail=join_to_ban.innomail,
            )

        logger.info(
            f"User banned successfully | banned_user_id={join_to_ban.user_id} gmail={join_to_ban.gmail} slug={slug}"
        )

        return BanUserResponse(
            message=f"Successfully banned {join_to_ban.user_id}",
        )

    except HTTPException:
        raise
    except HttpError as e:
        logger.error(f"Google API error while banning user: {e}")
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error banning user | slug={slug} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files/{slug}/bans/{user_id}")
async def unban_user(
    slug: str,
    user_id: str,
    user_token_data: INH_TOKEN_AUTH,
) -> UnbanUserResponse:
    """Unban user by user_id (author only)."""
    try:
        file = await google_file_repository.get_by_slug(slug)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        verify_file_ownership(file, user_token_data.innohassle_id)

        try:
            user_oid = PydanticObjectId(user_id)
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="Invalid user_id")

        await google_file_repository.unban_user_from_file(slug=slug, user_id=user_oid)
        return UnbanUserResponse(message=f"Successfully unbanned {user_id}")
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error unbanning user | slug={slug} user_id={user_id} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/{slug}/cleanup")
async def cleanup_file_permissions(
    slug: str,
    user_token_data: INH_TOKEN_AUTH,
) -> CleanupResponse:
    """Remove any user permissions that are not present in sso_joins."""
    try:
        file = await google_file_repository.get_by_slug(slug)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        verify_file_ownership(file, user_token_data.innohassle_id)

        from src.guard.modules.google_.service import drive_service

        drive = drive_service()
        perms = drive.permissions().list(fileId=file.file_id, fields="permissions(id,type,emailAddress)").execute()

        allowed_emails = {j.gmail for j in file.sso_joins}
        removed = 0
        for p in perms.get("permissions", []):
            if p.get("type") != "user":
                continue
            email = p.get("emailAddress")
            if not email:
                continue
            if email not in allowed_emails:
                try:
                    drive.permissions().delete(fileId=file.file_id, permissionId=p["id"]).execute()
                    removed += 1
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Error removing permission {p['id']} from {email}: {e}")

        return CleanupResponse(removed=removed)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"Cleanup file permissions error for {slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/files/{slug}/joins/{user_id}/role")
async def update_user_role(
    slug: str,
    user_id: str,
    request: UpdateUserRoleRequest,
    user_token_data: INH_TOKEN_AUTH,
) -> UpdateUserRoleResponse:
    """Update individual user role in the file."""
    try:
        file = await google_file_repository.get_by_slug(slug)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        verify_file_ownership(file, user_token_data.innohassle_id)

        try:
            user_oid = PydanticObjectId(user_id)
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="Invalid user_id")

        join_to_update = None
        for join in file.sso_joins:
            if join.user_id == user_oid:
                join_to_update = join
                break

        if not join_to_update:
            raise HTTPException(status_code=404, detail=f"User with user_id {user_id} not found in joins")

        if not join_to_update.permission_id:
            raise HTTPException(status_code=400, detail="User does not have a permission_id")

        logger.info(
            f"Updating user role | author_id={user_token_data.innohassle_id} "
            f"user_id={user_id} slug={slug} new_role={request.role}"
        )

        update_user_permission(file.file_id, join_to_update.permission_id, request.role)

        await google_file_repository.update_user_role(slug=slug, user_id=user_oid, role=request.role)

        logger.info(f"User role updated successfully | user_id={user_id} slug={slug} role={request.role}")

        return UpdateUserRoleResponse(message=f"Successfully updated role for user {user_id}")

    except HTTPException:
        raise
    except HttpError as e:
        logger.error(f"Google API error while updating user role: {e}")
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error updating user role | slug={slug} user_id={user_id} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/files/{slug}/role")
async def update_default_role(
    slug: str,
    request: UpdateDefaultRoleRequest,
    user_token_data: INH_TOKEN_AUTH,
) -> UpdateDefaultRoleResponse:
    """Update default role for the file and update all existing user roles."""
    try:
        file = await google_file_repository.get_by_slug(slug)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        verify_file_ownership(file, user_token_data.innohassle_id)

        logger.info(
            f"Updating default role | author_id={user_token_data.innohassle_id} slug={slug} new_role={request.role}"
        )

        updated_count = update_all_user_permissions(file.file_id, request.role, file.sso_joins)

        await google_file_repository.update_default_role(slug=slug, role=request.role)

        for join in file.sso_joins:
            await google_file_repository.update_user_role(slug=slug, user_id=join.user_id, role=request.role)

        logger.info(
            f"Default role updated successfully | slug={slug} role={request.role} updated_permissions={updated_count}"
        )

        return UpdateDefaultRoleResponse(
            message=f"Successfully updated default role to {request.role} and updated {updated_count} user permissions"
        )

    except HTTPException:
        raise
    except HttpError as e:
        logger.error(f"Google API error while updating default role: {e}")
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error updating default role | slug={slug} error={e}")
        raise HTTPException(status_code=500, detail=str(e))
