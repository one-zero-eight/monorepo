import pytest

from src.room_booking.modules.bookings.exchange_repository import EMAIL_IN_LOCATION_RE


@pytest.mark.parametrize(
    "location",
    [
        "Lecture room 301 (r.belkov@innopolis.university)",
        "Room 101 (a.b@innopolis.ru)",
        " (x@innopolis.university)",
    ],
)
def test_email_in_location_matches_innopolis_emails(location: str) -> None:
    assert EMAIL_IN_LOCATION_RE.search(location) is not None


@pytest.mark.parametrize(
    "location",
    [
        "Lecture room 301",
        "Room (user@gmail.com)",
        "user@innopolis.university",
        "",
    ],
)
def test_email_in_location_rejects_non_innopolis(location: str) -> None:
    assert EMAIL_IN_LOCATION_RE.search(location) is None


def test_email_in_location_group1_extracts_email() -> None:
    m = EMAIL_IN_LOCATION_RE.search("Lecture room 301 (r.belkov@innopolis.university)")
    assert m is not None and m.group(1) == "r.belkov@innopolis.university"
