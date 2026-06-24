from urllib.parse import parse_qsl, urlparse

import pytest
from fastapi import HTTPException

from src.forms.modules.links import routes as links_routes
from src.forms.modules.links.schemas import SignaturePayload


def test_validate_yandex_ru_url():
    result = links_routes._validate_yandex_forms_url("https://forms.yandex.ru/u/0123456789abcdef")
    assert result == "https://forms.yandex.ru/u/0123456789abcdef"


def test_validate_yandex_com_cloud_normalized_to_ru():
    result = links_routes._validate_yandex_forms_url("https://forms.yandex.com/cloud/deadbeef")
    assert result == "https://forms.yandex.ru/cloud/deadbeef"


def test_validate_rejects_ftp_scheme():
    with pytest.raises(HTTPException) as exc:
        links_routes._validate_yandex_forms_url("ftp://forms.yandex.ru/u/0123456789abcdef")
    assert exc.value.status_code == 422
    assert exc.value.detail == "Only http/https URLs are allowed"


def test_validate_rejects_bad_host():
    with pytest.raises(HTTPException) as exc:
        links_routes._validate_yandex_forms_url("https://evil.example/u/0123456789abcdef")
    assert exc.value.status_code == 422
    assert exc.value.detail == "URL host is not allowed"


def test_validate_rejects_bad_path():
    with pytest.raises(HTTPException) as exc:
        links_routes._validate_yandex_forms_url("https://forms.yandex.ru/forms/not-hex")
    assert exc.value.status_code == 422
    assert exc.value.detail == "URL path must start with /u/ or /cloud/"


def test_build_prefilled_url_includes_query_params():
    payload = SignaturePayload(
        email="user@innopolis.university",
        fio="Test User",
        telegram="@telegram",
    )
    signature = "payload.sig"
    url = links_routes._build_prefilled_url(
        "https://forms.yandex.ru/u/0123456789abcdef",
        payload,
        signature,
    )
    query = dict(parse_qsl(urlparse(url).query))
    assert query["email"] == payload.email
    assert query["fio"] == payload.fio
    assert query["telegram"] == payload.telegram
    assert query["s"] == signature
