"""Map Excel distribution labels onto schedule-assistant student group codes."""

import re
from collections.abc import Callable, Sequence

from src.schedule_assistant.modules.schedule_config.schemas import SectionConfig, StudentsGroups

# Collapse whitespace and common separators so "AWA-I 10" matches "AWA-I-10",
# and "EAP6" matches "EAP-6".
_SEPARATOR_RE = re.compile(r"[\s\-_/·•]+")


def normalize_label(value: str) -> str:
    return _SEPARATOR_RE.sub("", value.replace("\xa0", " ")).casefold()


def iter_section_group_codes(section: SectionConfig) -> list[str]:
    """Group codes in program / track declaration order (deduped)."""
    codes: list[str] = []
    seen: set[str] = set()
    for program in section.programs:
        for group_code in program.groups:
            if not group_code or group_code in seen:
                continue
            seen.add(group_code)
            codes.append(group_code)
        for track in program.tracks:
            for group_code in track.groups:
                if not group_code or group_code in seen:
                    continue
                seen.add(group_code)
                codes.append(group_code)
    return codes


def collect_section_group_codes(section: SectionConfig) -> set[str]:
    return set(iter_section_group_codes(section))


def section_target_groups(
    section: SectionConfig,
    students_groups: list[StudentsGroups],
) -> list[StudentsGroups]:
    by_code = {group.code: group for group in students_groups}
    return [by_code[code] for code in iter_section_group_codes(section) if code in by_code]


def suggest_mapping(
    excel_labels: list[str],
    target_groups: list[StudentsGroups],
) -> dict[str, str | None]:
    """Suggest excel_label -> group_code with best-effort normalization.

    Year-shift near-misses (B24 vs B25) stay unmapped. Ambiguous normalized
    matches (two targets collapse to the same key) are ignored.
    """
    by_exact: dict[str, str] = {}
    by_normalized: dict[str, str] = {}
    ambiguous_normalized: set[str] = set()

    def _register_normalized(key: str, code: str) -> None:
        if key in ambiguous_normalized:
            return
        existing = by_normalized.get(key)
        if existing is None:
            by_normalized[key] = code
            return
        if existing != code:
            ambiguous_normalized.add(key)
            by_normalized.pop(key, None)

    for group in target_groups:
        by_exact[group.code.casefold()] = group.code
        _register_normalized(normalize_label(group.code), group.code)
        if group.name:
            by_exact[group.name.casefold()] = group.code
            _register_normalized(normalize_label(group.name), group.code)

    mapping: dict[str, str | None] = {}
    for label in excel_labels:
        code = by_exact.get(label.casefold())
        if code is None:
            code = by_normalized.get(normalize_label(label))
        mapping[label] = code
    return mapping


def sort_labels_by_suggested_mapping[TLabel](
    labels: Sequence[TLabel],
    *,
    label_of: Callable[[TLabel], str],
    suggested_mapping: dict[str, str | None],
    target_group_codes: Sequence[str],
) -> list[TLabel]:
    """Unmatched first; matched follow target group order. Stable within buckets.

    Sort once from suggested mapping — callers should not re-run after manual
    remapping.
    """
    group_order = {code: index for index, code in enumerate(target_group_codes)}
    fallback = len(group_order)

    def sort_key(indexed: tuple[int, TLabel]) -> tuple[int, int, int]:
        original_index, item = indexed
        code = suggested_mapping.get(label_of(item))
        if not code:
            return (0, original_index, 0)
        return (1, group_order.get(code, fallback), original_index)

    return [item for _, item in sorted(enumerate(labels), key=sort_key)]
