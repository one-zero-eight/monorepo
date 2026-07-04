from urllib.parse import unquote

from fastapi import APIRouter, Body
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from pydantic import BaseModel

from src.schedule.dependencies import VERIFY_PARSER_DEPENDENCY
from src.schedule.exceptions import IncorrectCredentialsException
from src.schedule.modules.tags.repository import tag_repository
from src.schedule.modules.tags.schemas import CreateTag, ViewTag

router = APIRouter(prefix="/tags", tags=["Tags"], route_class=AutoDeriveResponsesAPIRoute)


class ListTagsResponse(BaseModel):
    tags: list[ViewTag]


@router.get(
    "/",
    responses={
        200: {"description": "List of event groups", "model": ListTagsResponse},
    },
)
async def list_tags() -> ListTagsResponse:
    """
    Get a list of all tags
    """
    tags = await tag_repository.read_all()
    return ListTagsResponse(tags=tags)


@router.post(
    "/batch-create-or-read",
    responses={
        200: {"description": "List of created or existing tags", "model": ListTagsResponse},
        **IncorrectCredentialsException.responses,
    },
)
async def batch_create_tags(_: VERIFY_PARSER_DEPENDENCY, tags: list[CreateTag] = Body(embed=True)) -> ListTagsResponse:
    """
    Create tags in batch
    """
    created_tags = await tag_repository.batch_create_or_read(tags)
    return ListTagsResponse(tags=created_tags)


@router.delete(
    "/by-alias",
    responses={
        200: {"description": "Tag deleted successfully"},
        **IncorrectCredentialsException.responses,
    },
)
async def delete_tag(tag_alias: str, _: VERIFY_PARSER_DEPENDENCY) -> None:
    """
    Delete tag by alias
    """
    tag_alias = unquote(tag_alias)
    await tag_repository.delete_by_alias(tag_alias)


@router.delete(
    "/by-type",
    responses={
        200: {"description": "Tag deleted successfully"},
        **IncorrectCredentialsException.responses,
    },
)
async def delete_tag_by_type(tag_type: str, _: VERIFY_PARSER_DEPENDENCY) -> None:
    """
    Delete tag by type
    """
    await tag_repository.delete_by_type(tag_type)
