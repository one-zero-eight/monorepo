from src.schedule_assistant.modules.schedule_config.schemas import ScheduleConfig


def teaching_days(cfg: ScheduleConfig) -> list[str]:
    configured_days = list(dict.fromkeys(cfg.term.days))
    if not configured_days:
        return []
    start_day = cfg.term.starting_day
    if start_day not in configured_days:
        return [day.value for day in configured_days]
    start_idx = configured_days.index(start_day)
    ordered = configured_days[start_idx:] + configured_days[:start_idx]
    return [day.value for day in ordered]
