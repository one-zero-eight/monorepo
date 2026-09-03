from pathlib import Path

from src.schedule_assistant.modules.distributions.mapping import (
    normalize_label,
    sort_labels_by_suggested_mapping,
    suggest_mapping,
)
from src.schedule_assistant.modules.distributions.parser import parse_distribution_xlsx
from src.schedule_assistant.modules.schedule_config.schemas import StudentsGroups

FIXTURES = Path(__file__).parent / "fixtures" / "distributions"
REAL_ENGLISH = Path(__file__).resolve().parents[2] / "Foreign language.xlsx"
REAL_CORE = Path(__file__).resolve().parents[2] / "КонтингентИДвижение_13_03_26.xlsx"
REAL_ELECTIVES = Path(__file__).resolve().parents[2] / "Spring26 Electives Distribution.xlsx"


def test_parse_core_contingent_detects_email_and_group() -> None:
    parsed = parse_distribution_xlsx((FIXTURES / "core_contingent.xlsx").read_bytes())
    assert parsed.email_column == "Доменный идентификатор"
    assert parsed.membership_columns == ["Учебная группа"]
    assert parsed.email_count == 3
    assert {label.label for label in parsed.labels} == {"B25-CSE-01", "B24-CBS-02"}
    assert parsed.emails_by_label["B25-CSE-01"] == [
        "a.ivanov@innopolis.university",
        "p.petrov@innopolis.university",
    ]


def test_parse_english_detects_e_group() -> None:
    parsed = parse_distribution_xlsx((FIXTURES / "english_foreign.xlsx").read_bytes())
    assert parsed.email_column == "E-mail"
    assert parsed.membership_columns == ["E Group"]
    assert parsed.email_count == 3
    assert parsed.emails_by_label["AWA-I 10"] == [
        "a.lovelace@innopolis.university",
        "a.turing@innopolis.university",
    ]
    assert parsed.emails_by_label["EAP6"] == ["g.hopper@innopolis.university"]


def test_parse_electives_prefers_elective_columns_and_unions() -> None:
    parsed = parse_distribution_xlsx(
        (FIXTURES / "electives_distribution.xlsx").read_bytes(),
        sheet_name="BS2 RU",
    )
    assert parsed.email_column == "E-mail"
    assert parsed.membership_columns == ["Электив 1", "Электив 2"]
    assert "Углубленный Python" in parsed.emails_by_label
    assert set(parsed.emails_by_label["Углубленный Python"]) == {
        "s.one@innopolis.university",
        "s.two@innopolis.university",
    }
    assert set(parsed.emails_by_label["Основы робототехники"]) == {
        "s.one@innopolis.university",
        "s.three@innopolis.university",
    }


def test_parse_electives_bs3_ignores_academic_group_column() -> None:
    parsed = parse_distribution_xlsx(
        (FIXTURES / "electives_distribution.xlsx").read_bytes(),
        sheet_name="BS3",
    )
    assert parsed.membership_columns == ["Tech Elective"]
    assert "B23-AI-01" not in parsed.emails_by_label
    assert parsed.emails_by_label["Introduction to DevOps"] == ["s.four@innopolis.university"]
    assert parsed.emails_by_label["CPython Advanced"] == ["s.five@innopolis.university"]


def test_suggest_mapping_exact_and_normalized_not_year_shift() -> None:
    targets = [
        StudentsGroups(code="B25-CSE-01", name="CSE 01"),
        StudentsGroups(
            code="AWA-I-10",
        ),
        StudentsGroups(code="python-adv", name="Углубленный Python"),
    ]
    mapping = suggest_mapping(
        ["B25-CSE-01", "B24-CSE-01", "AWA-I 10", "Углубленный Python"],
        targets,
    )
    assert mapping["B25-CSE-01"] == "B25-CSE-01"
    assert mapping["B24-CSE-01"] is None
    assert mapping["AWA-I 10"] == "AWA-I-10"
    assert mapping["Углубленный Python"] == "python-adv"


def test_normalize_label_collapses_separators() -> None:
    assert normalize_label("AWA-I 10") == normalize_label("AWA-I-10")
    assert normalize_label("EAP6") == normalize_label("EAP-6")
    assert normalize_label("FL 3") == normalize_label("FL-3")
    assert normalize_label("AWA-I\xa010") == normalize_label("AWA-I-10")


def test_suggest_mapping_english_spacing_and_hyphen_variants() -> None:
    targets = [
        StudentsGroups(
            code="AWA-I-1",
        ),
        StudentsGroups(
            code="AWA-I-10",
        ),
        StudentsGroups(
            code="EAP-6",
        ),
        StudentsGroups(
            code="FL-3",
        ),
    ]
    mapping = suggest_mapping(
        ["AWA-I 10", "EAP6", "AWA-I 1", "FL 3", "AWA-I 99"],
        targets,
    )
    assert mapping == {
        "AWA-I 10": "AWA-I-10",
        "EAP6": "EAP-6",
        "AWA-I 1": "AWA-I-1",
        "FL 3": "FL-3",
        "AWA-I 99": None,
    }


def test_suggest_mapping_skips_ambiguous_normalized_targets() -> None:
    targets = [
        StudentsGroups(
            code="G1",
        ),
        StudentsGroups(
            code="G-1",
        ),
    ]
    mapping = suggest_mapping(["G 1"], targets)
    assert mapping["G 1"] is None


def test_sort_labels_unmatched_first_then_program_order() -> None:
    labels: list[dict[str, str | int]] = [
        {"label": "EAP6", "email_count": 3},
        {"label": "Unknown", "email_count": 1},
        {"label": "AWA-I 10", "email_count": 2},
        {"label": "Also Unknown", "email_count": 4},
    ]
    suggested = {
        "EAP6": "EAP-6",
        "Unknown": None,
        "AWA-I 10": "AWA-I-10",
        "Also Unknown": None,
    }
    ordered = sort_labels_by_suggested_mapping(
        labels,
        label_of=lambda item: str(item["label"]),
        suggested_mapping=suggested,
        target_group_codes=["AWA-I-10", "EAP-6", "FL-3"],
    )
    assert [item["label"] for item in ordered] == [
        "Unknown",
        "Also Unknown",
        "AWA-I 10",
        "EAP6",
    ]


def test_forged_core_messy_header_nbsp_and_casefold() -> None:
    parsed = parse_distribution_xlsx((FIXTURES / "forged_core_messy.xlsx").read_bytes())
    assert parsed.header_row_index == 2
    assert parsed.email_column == "Доменный идентификатор"
    assert parsed.membership_columns == ["Учебная группа"]
    assert parsed.email_count == 3
    assert parsed.emails_by_label["B25-CSE-01"] == [
        "a.ivanov@innopolis.university",
        "p.petrov@innopolis.university",
    ]
    # Group code case from excel preserved as label key; mapping normalizes separately.
    assert "b24-cbs-02" in parsed.emails_by_label
    assert parsed.emails_by_label["b24-cbs-02"] == ["a.sidorova@innopolis.university"]
    assert "B25-CSE-99" not in parsed.emails_by_label


def test_forged_english_maps_to_hyphenated_codes() -> None:
    parsed = parse_distribution_xlsx((FIXTURES / "forged_english_spacing.xlsx").read_bytes())
    assert parsed.email_column == "E-mail"
    assert parsed.membership_columns == ["E Group"]
    assert set(parsed.emails_by_label) == {"AWA-I 10", "EAP6", "AWA-I 1", "FL 3"}

    targets = [
        StudentsGroups(
            code="AWA-I-1",
        ),
        StudentsGroups(
            code="AWA-I-10",
        ),
        StudentsGroups(
            code="EAP-6",
        ),
        StudentsGroups(
            code="FL-3",
        ),
    ]
    mapping = suggest_mapping([item.label for item in parsed.labels], targets)
    assert mapping["AWA-I 10"] == "AWA-I-10"
    assert mapping["EAP6"] == "EAP-6"
    assert mapping["AWA-I 1"] == "AWA-I-1"
    assert mapping["FL 3"] == "FL-3"


def test_forged_electives_multisheet_and_hum_column() -> None:
    raw = (FIXTURES / "forged_electives_multisheet.xlsx").read_bytes()
    bs2 = parse_distribution_xlsx(raw, sheet_name="BS2 RU")
    assert bs2.header_row_index == 1
    assert bs2.membership_columns == ["Электив 1", "Электив 2"]
    assert bs2.email_count == 3

    bs3 = parse_distribution_xlsx(raw, sheet_name="BS3")
    assert "Tech Elective" in bs3.membership_columns
    assert "Hum Elective" in bs3.membership_columns
    assert "Group" not in bs3.membership_columns
    assert set(bs3.emails_by_label["Introduction to DevOps"]) == {
        "s.four@innopolis.university",
        "s.six@innopolis.university",
    }
    assert bs3.emails_by_label["Philosophy"] == [
        "s.four@innopolis.university",
        "s.five@innopolis.university",
    ]


def test_forged_email_column_detected_by_cell_content() -> None:
    parsed = parse_distribution_xlsx((FIXTURES / "forged_email_by_content.xlsx").read_bytes())
    assert parsed.email_column == "Contact"
    assert parsed.membership_columns == ["Bucket"]
    assert parsed.emails_by_label["G1"] == [
        "a@innopolis.university",
        "b@innopolis.university",
    ]
    assert "A" not in parsed.emails_by_label
    assert "B" not in parsed.emails_by_label


def test_real_foreign_language_xlsx_maps_to_hyphenated_english_codes() -> None:
    if not REAL_ENGLISH.exists():
        return
    parsed = parse_distribution_xlsx(REAL_ENGLISH.read_bytes())
    assert parsed.email_column == "E-mail"
    assert parsed.membership_columns == ["E Group"]
    assert parsed.email_count > 100
    assert "AWA-I 10" in parsed.emails_by_label
    assert "EAP6" in parsed.emails_by_label or any(normalize_label(label) == "eap6" for label in parsed.emails_by_label)

    targets = [
        StudentsGroups(
            code=f"AWA-I-{n}",
        )
        for n in range(1, 17)
    ] + [
        StudentsGroups(
            code=f"EAP-{n}",
        )
        for n in (1, 2, 3, 4, 6, 7, 8, 9, 10, 11)
    ]
    mapping = suggest_mapping([item.label for item in parsed.labels], targets)
    assert mapping.get("AWA-I 10") == "AWA-I-10"
    assert mapping.get("AWA-I 1") == "AWA-I-1"
    # At least half of excel labels should best-effort map into the known set.
    mapped = sum(1 for code in mapping.values() if code)
    assert mapped >= len(mapping) // 2


def test_real_contingent_xlsx_parses_groups() -> None:
    if not REAL_CORE.exists():
        return
    parsed = parse_distribution_xlsx(REAL_CORE.read_bytes())
    assert parsed.email_column == "Доменный идентификатор"
    assert parsed.membership_columns == ["Учебная группа"]
    assert parsed.email_count > 100
    assert any(label.startswith(("B25-", "B24-")) for label in parsed.emails_by_label)


def test_real_electives_xlsx_prefers_elective_columns() -> None:
    if not REAL_ELECTIVES.exists():
        return
    parsed = parse_distribution_xlsx(REAL_ELECTIVES.read_bytes(), sheet_name="BS3")
    assert parsed.email_column == "E-mail"
    assert "Tech Elective" in parsed.membership_columns
    assert "Group" not in parsed.membership_columns
    assert parsed.email_count > 50
