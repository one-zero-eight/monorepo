import datetime as dtm

from src.schedule_assistant.modules.schedule_config.schemas import (
    CoursesConfig,
    RoomAttributeDef,
    RoomConfig,
    TermConfig,
)
from src.schedule_assistant.modules.schedule_config.validation import (
    validate_rooms,
    validate_term,
)


def _term(*, room_attributes: list[RoomAttributeDef] | None = None) -> TermConfig:
    return TermConfig(
        name="Test",
        semester=TermConfig.DateRange(
            start_date=dtm.date(2026, 9, 1),
            end_date=dtm.date(2026, 12, 31),
        ),
        room_attributes=room_attributes or [],
    )


def test_validate_term_rejects_duplicate_room_attribute_keys() -> None:
    term = _term(
        room_attributes=[
            RoomAttributeDef(key="projector", type="boolean"),
            RoomAttributeDef(key="projector", type="string"),
        ]
    )
    errors = validate_term(term)
    assert any("is duplicated" in error for error in errors)


def test_validate_term_rejects_enum_without_values() -> None:
    term = _term(room_attributes=[RoomAttributeDef(key="board", type="enum", enum_values=[])])
    errors = validate_term(term)
    assert any("enum_values must not be empty" in error for error in errors)


def test_validate_term_rejects_non_null_default() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RoomAttributeDef.model_validate(
            {
                "key": "board",
                "type": "enum",
                "enum_values": ["white", "black"],
                "default": "white",
            }
        )


def test_validate_rooms_rejects_unknown_feature_key() -> None:
    term = _term(room_attributes=[RoomAttributeDef(key="projector", type="boolean")])
    rooms = RoomConfig(
        rooms=[RoomConfig.Room(id="101", name="101", features={"outlets": True})],
    )
    errors = validate_rooms(rooms, courses=CoursesConfig(), term=term)
    assert any("unknown key 'outlets'" in error for error in errors)


def test_validate_rooms_rejects_wrong_feature_type() -> None:
    term = _term(room_attributes=[RoomAttributeDef(key="capacity_note", type="number")])
    rooms = RoomConfig(
        rooms=[RoomConfig.Room(id="101", name="101", features={"capacity_note": "large"})],
    )
    errors = validate_rooms(rooms, courses=CoursesConfig(), term=term)
    assert any("invalid type for number" in error for error in errors)


def test_validate_rooms_rejects_enum_value_outside_list() -> None:
    term = _term(room_attributes=[RoomAttributeDef(key="board", type="enum", enum_values=["white", "black"])])
    rooms = RoomConfig(
        rooms=[RoomConfig.Room(id="101", name="101", features={"board": "green"})],
    )
    errors = validate_rooms(rooms, courses=CoursesConfig(), term=term)
    assert any("is not in enum_values" in error for error in errors)


def test_validate_rooms_allows_matching_features() -> None:
    term = _term(
        room_attributes=[
            RoomAttributeDef(key="projector", type="boolean"),
            RoomAttributeDef(key="board", type="enum", enum_values=["white", "black"]),
            RoomAttributeDef(key="outlets", type="number"),
            RoomAttributeDef(key="note", type="string"),
        ]
    )
    rooms = RoomConfig(
        rooms=[
            RoomConfig.Room(
                id="101",
                name="101",
                features={"projector": True, "board": "black", "outlets": 4, "note": "ok"},
            )
        ],
    )
    assert validate_rooms(rooms, courses=CoursesConfig(), term=term) == []


def test_validate_rooms_allows_partial_features_without_defaults() -> None:
    term = _term(
        room_attributes=[
            RoomAttributeDef(key="projector", type="boolean"),
            RoomAttributeDef(key="board", type="enum", enum_values=["white", "black"]),
        ]
    )
    rooms = RoomConfig(
        rooms=[RoomConfig.Room(id="101", name="101", features={"projector": True})],
    )
    assert validate_rooms(rooms, courses=CoursesConfig(), term=term) == []


def test_validate_rooms_allows_list_features() -> None:
    term = _term(room_attributes=[RoomAttributeDef(key="tags", type="list")])
    rooms = RoomConfig(
        rooms=[RoomConfig.Room(id="101", name="101", features={"tags": ["a", "b"]})],
    )
    assert validate_rooms(rooms, courses=CoursesConfig(), term=term) == []


def test_validate_rooms_rejects_invalid_list_features() -> None:
    term = _term(room_attributes=[RoomAttributeDef(key="tags", type="list")])
    rooms = RoomConfig(
        rooms=[RoomConfig.Room(id="101", name="101", features={"tags": "a"})],  # type: ignore[dict-item]
    )
    errors = validate_rooms(rooms, courses=CoursesConfig(), term=term)
    assert any("invalid type for list" in error for error in errors)


def test_validate_rooms_skips_feature_check_when_defs_empty() -> None:
    term = _term(room_attributes=[])
    rooms = RoomConfig(
        rooms=[RoomConfig.Room(id="101", name="101", features={"anything": True})],
    )
    assert validate_rooms(rooms, courses=CoursesConfig(), term=term) == []
