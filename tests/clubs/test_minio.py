class _FakeBaseUrl:
    def build(self, **kwargs):
        object_name = kwargs["object_name"]
        return ("https", "cdn.test", f"/{object_name}", "", "")


class _FakeMinioClient:
    def __init__(self):
        self._base_url = _FakeBaseUrl()
        self.put_calls = []

    def _get_region(self, _bucket: str):
        return "us-east-1"

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)


def test_get_club_logo_object_name():
    from src.clubs import minio as clubs_minio

    assert clubs_minio.get_club_logo_object_name("abc") == "logos/abc"
    assert clubs_minio.get_club_logo_object_name("abc", 512) == "logos/abc-512"


def test_get_club_logo_url(monkeypatch):
    from src.clubs import minio as clubs_minio

    fake_client = _FakeMinioClient()
    monkeypatch.setattr(clubs_minio, "minio_client", fake_client)

    url = clubs_minio.get_club_logo_url("logo-1", 512)
    assert url == "https://cdn.test/logos/logo-1-512"


def test_put_club_logo(monkeypatch):
    from src.clubs import minio as clubs_minio

    fake_client = _FakeMinioClient()
    monkeypatch.setattr(clubs_minio, "minio_client", fake_client)

    clubs_minio.put_club_logo("logo-2", None, b"png-bytes", "image/png")

    assert len(fake_client.put_calls) == 1
    call = fake_client.put_calls[0]
    assert call["bucket_name"] == clubs_minio.settings.minio.bucket
    assert call["object_name"] == "logos/logo-2"
    assert call["length"] == len(b"png-bytes")
    assert call["content_type"] == "image/png"
