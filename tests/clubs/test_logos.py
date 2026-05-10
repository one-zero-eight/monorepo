from urllib.parse import urlparse

from fastapi.testclient import TestClient

from src.clubs.modules.clubs.logos_repo import logos_repo


def test_get_club_logo_object_name(clubs_client: TestClient):
    assert logos_repo.get_club_logo_object_name("abc") == "logos/abc"
    assert logos_repo.get_club_logo_object_name("abc", 512) == "logos/abc-512"


def test_get_club_logo_url(clubs_client: TestClient):
    url = logos_repo.get_club_logo_url("logo-1", 512)
    parsed = urlparse(url)
    assert parsed.scheme in {"http", "https"}
    assert "logos/logo-1-512" in url


def test_put_club_logo(clubs_client: TestClient):
    logos_repo.put_club_logo("logo-2", None, b"png-bytes", "image/png")

    obj = logos_repo.minio_client.get_object(logos_repo.bucket, "logos/logo-2")
    try:
        assert obj.read() == b"png-bytes"
    finally:
        obj.close()
        obj.release_conn()
