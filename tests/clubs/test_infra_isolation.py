"""Isolation resets shared Mongo collections and MinIO bucket contents (see ``conftest``)."""

import io
import uuid
from typing import cast

import pytest
from fastapi.testclient import TestClient

from src.clubs.mongo import Club, ClubType

OBJECT_PREFIX = "infra-probe/"


async def _club_count() -> int:
    return await Club.count()


async def _insert_probe_club(slug: str) -> None:
    await Club(
        slug=slug,
        title="infra isolation probe",
        short_description="s",
        description="d",
        type=ClubType.TECH,
    ).insert()


@pytest.mark.parametrize("_run", range(3))
def test_clubs_cleanup_gives_empty_mongo_then_one_club_visible(
    clubs_client: TestClient,
    _run: int,
) -> None:
    portal = clubs_client.portal
    assert portal is not None
    assert portal.call(_club_count) == 0

    slug = f"infra-iso-{uuid.uuid4().hex}"
    portal.call(_insert_probe_club, slug)
    assert portal.call(_club_count) == 1

    async def _load_slug_back() -> str | None:
        doc = await Club.find_one(Club.slug == slug)
        return doc.slug if doc else None

    assert portal.call(_load_slug_back) == slug


@pytest.mark.parametrize("_run", range(3))
def test_clubs_cleanup_gives_empty_minio_prefix_then_one_object(
    clubs_client: TestClient,
    _run: int,
) -> None:
    from fastapi import FastAPI

    minio = cast(FastAPI, clubs_client.app).state.minio_store
    bucket = minio.bucket_name
    mc = minio.client

    listed = list(mc.list_objects(bucket, prefix=OBJECT_PREFIX, recursive=True))
    assert listed == []

    key = f"{OBJECT_PREFIX}{uuid.uuid4().hex}.bin"
    payload = key.encode()
    mc.put_object(bucket, key, io.BytesIO(payload), length=len(payload))

    after = list(mc.list_objects(bucket, prefix=OBJECT_PREFIX, recursive=True))
    assert len(after) == 1
    assert after[0].object_name == key

    obj = mc.get_object(bucket, key)
    try:
        assert obj.read() == payload
    finally:
        obj.close()
        obj.release_conn()
