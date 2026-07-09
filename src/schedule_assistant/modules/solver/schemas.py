import datetime as dtm
from pathlib import Path
from typing import Literal

from pydantic import Field

from src.schedule_assistant.modules.schedule_config.schemas import CoursesConfig, SettingBaseModel


class SolveStats(SettingBaseModel):
    class PhaseStats(SettingBaseModel):
        phase: str
        decision: str
        solver_status: str | None = None
        objective_value: float | None = None
        best_objective_bound: float | None = None
        max_time_in_seconds: float | None = None
        solver_parameters: str | None = None
        variable_count: int | None = None
        constraint_count: int | None = None
        response_stats: str | None = None
        solution_info: str | None = None

    meetings: int
    slots: int
    error: str | None = None
    started_at: dtm.datetime | None = None
    saved_at: dtm.datetime | None = None
    elapsed_seconds: float | None = None
    slots_per_day: int | None = None
    teaching_days: int | None = None
    phase_stats: list[PhaseStats] = Field(default_factory=list)


class SolveResult(SettingBaseModel):
    status: Literal["OPTIMAL", "INFEASIBLE", "FEASIBLE", "MODEL_INVALID", "UNKNOWN", "EMPTY"]
    stats: SolveStats
    artifacts_dir: Path | None = None
    schedule: CoursesConfig
