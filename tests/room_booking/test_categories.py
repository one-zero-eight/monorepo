from src.room_booking.modules.bookings.categories import sanitize_exchange_categories, sanitize_exchange_category


def test_sanitize_exchange_category_keeps_ascii() -> None:
    assert sanitize_exchange_category("Statistics with Applications") == "Statistics with Applications"


def test_sanitize_exchange_category_strips_cyrillic() -> None:
    name = (
        "Methods and Approaches to the Launch of Robotic Systems / Методы и подходы к запуску роботизированных систем"
    )
    assert sanitize_exchange_category(name) == "Methods and Approaches to the Launch of Robotic Systems"


def test_sanitize_exchange_category_replaces_commas_and_semicolons() -> None:
    assert sanitize_exchange_category("foo, bar; baz") == "foo bar baz"


def test_sanitize_exchange_category_truncates_long_values() -> None:
    assert len(sanitize_exchange_category("x" * 300)) == 255


def test_sanitize_exchange_categories_skips_empty_after_cleaning() -> None:
    assert sanitize_exchange_categories(["Auto", "Методы"]) == ["Auto"]


def test_sanitize_exchange_categories_none_and_empty() -> None:
    assert sanitize_exchange_categories(None) is None
    assert sanitize_exchange_categories([]) == []
