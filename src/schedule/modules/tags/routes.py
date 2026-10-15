from typing import Annotated
from urllib.parse import unquote

from fastapi import APIRouter, Body
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from pydantic import BaseModel

from src.schedule.db import TagRepoDep
from src.schedule.dependencies import VerifyParserDep
from src.schedule.exceptions import IncorrectCredentialsException
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
async def list_tags(tag_repo: TagRepoDep) -> ListTagsResponse:
    """
    Get a list of all tags
    """
    tags = await tag_repo.read_all()
    return ListTagsResponse(tags=tags)


@router.post(
    "/batch-create-or-read",
    responses={
        200: {"description": "List of created or existing tags", "model": ListTagsResponse},
        **IncorrectCredentialsException.responses,
    },
)
async def batch_create_tags(
    _: VerifyParserDep,
    tag_repo: TagRepoDep,
    tags: Annotated[list[CreateTag], Body(embed=True)],
) -> ListTagsResponse:
    """
    Create tags in batch
    """
    created_tags = await tag_repo.batch_create_or_read(tags)
    return ListTagsResponse(tags=created_tags)


@router.delete(
    "/by-alias",
    responses={
        200: {"description": "Tag deleted successfully"},
        **IncorrectCredentialsException.responses,
    },
)
async def delete_tag(tag_alias: str, _: VerifyParserDep, tag_repo: TagRepoDep) -> None:
    """
    Delete tag by alias
    """
    tag_alias = unquote(tag_alias)
    await tag_repo.delete_by_alias(tag_alias)


@router.delete(
    "/by-type",
    responses={
        200: {"description": "Tag deleted successfully"},
        **IncorrectCredentialsException.responses,
    },
)
async def delete_tag_by_type(tag_type: str, _: VerifyParserDep, tag_repo: TagRepoDep) -> None:
    """
    Delete tag by type
    """
    await tag_repo.delete_by_type(tag_type)
