from typing import Any

from src.schedule_assistant.modules.schedule_config.schemas import ScheduleConfig, SectionsConfig
from src.schedule_assistant.modules.schedule_config.validation import build_selector_map, expand_group_tokens

# Removed from TermConfig / SectionProgram / ProgramTrack / RoomAttributeDef (extra="forbid").
_OBSOLETE_PROGRAM_KEYS = frozenset({"kind", "degree", "language", "year", "applies_to"})
_OBSOLETE_TRACK_KEYS = frozenset({"kind"})
_OBSOLETE_ROOM_ATTRIBUTE_KEYS = frozenset({"default"})


def sanitize_legacy_section(section: Any) -> Any:
    if not isinstance(section, dict):
        return section
    cleaned = dict(section)
    programs: list[Any] = []
    for program in cleaned.get("programs") or []:
        if not isinstance(program, dict):
            programs.append(program)
            continue
        program_clean = {key: value for key, value in program.items() if key not in _OBSOLETE_PROGRAM_KEYS}
        tracks: list[Any] = []
        for track in program.get("tracks") or []:
            if not isinstance(track, dict):
                tracks.append(track)
                continue
            tracks.append({key: value for key, value in track.items() if key not in _OBSOLETE_TRACK_KEYS})
        if "tracks" in program or tracks:
            program_clean["tracks"] = tracks
        programs.append(program_clean)
    cleaned["programs"] = programs
    return cleaned


def sanitize_legacy_room_attributes(attributes: Any) -> list[Any]:
    if not isinstance(attributes, list):
        return []
    cleaned: list[Any] = []
    for attribute in attributes:
        if not isinstance(attribute, dict):
            cleaned.append(attribute)
            continue
        cleaned.append({key: value for key, value in attribute.items() if key not in _OBSOLETE_ROOM_ATTRIBUTE_KEYS})
    return cleaned


def sanitize_legacy_term_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(payload)
    if "sections" in cleaned:
        cleaned["sections"] = [sanitize_legacy_section(section) for section in (cleaned["sections"] or [])]
    if "room_attributes" in cleaned:
        cleaned["room_attributes"] = sanitize_legacy_room_attributes(cleaned["room_attributes"])
    return cleaned


def sanitize_legacy_schedule_config_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(payload)
    if "sections" in cleaned and "term" not in cleaned:
        cleaned["sections"] = [sanitize_legacy_section(section) for section in (cleaned["sections"] or [])]
    term = cleaned.get("term")
    if isinstance(term, dict):
        cleaned["term"] = sanitize_legacy_term_payload(term)
    elif "sections" in cleaned:
        # Top-level sections (pre-nesting import shape).
        cleaned["sections"] = [sanitize_legacy_section(section) for section in (cleaned["sections"] or [])]
    return cleaned


def resolve_selector_map(cfg: ScheduleConfig) -> dict[str, set[str]]:
    sections = SectionsConfig(sections=cfg.term.sections, students_groups=cfg.students_groups)
    return build_selector_map(sections)


def expand_groups(tokens: list[str], selector_map: dict[str, set[str]]) -> list[str]:
    return sorted(expand_group_tokens(tokens, selector_map))
