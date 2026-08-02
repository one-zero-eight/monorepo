from src.schedule_assistant.core_courses.location_parser import extract_room_from_location_string


def test_extract_room_ignores_modifiers():
    assert extract_room_from_location_string("107 (ONLY ON 8/09, 29/09)") == "107"
    assert extract_room_from_location_string("313 (WEEK 1-3) / ONLINE") == "313"
    assert extract_room_from_location_string("460 EXCEPT 28/11") == "460"
    assert extract_room_from_location_string("ONLINE ON 13/09") == "ONLINE"
