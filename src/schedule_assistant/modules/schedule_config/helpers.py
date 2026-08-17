from src.schedule_assistant.modules.schedule_config.schemas import ScheduleConfig, SectionsConfig
from src.schedule_assistant.modules.schedule_config.validation import build_selector_map, expand_group_tokens


def resolve_selector_map(cfg: ScheduleConfig) -> dict[str, set[str]]:
    sections = SectionsConfig(sections=cfg.term.sections, students_groups=cfg.students_groups)
    return build_selector_map(sections)


def expand_groups(tokens: list[str], selector_map: dict[str, set[str]]) -> list[str]:
    return sorted(expand_group_tokens(tokens, selector_map))
