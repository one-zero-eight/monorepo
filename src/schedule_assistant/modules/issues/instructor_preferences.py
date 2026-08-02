from src.schedule_assistant.modules.issues.issue_text import attach_issue_text
from src.schedule_assistant.modules.issues.meetings import meeting_instructor_ids
from src.schedule_assistant.modules.issues.schemas import (
    InstructorBannedSlotIssue,
    InstructorPreferenceIssue,
    IssueTypeEnum,
    OccurrencePlacement,
    ScheduledMeeting,
    WeeklyPatternPlacement,
)
from src.schedule_assistant.modules.schedule_config.schemas import InstructorConfig, TermConfig
from src.schedule_assistant.modules.solver.instructor_preferences import (
    meeting_day_slot_cell,
    resolve_preference_grids,
)
from src.schedule_assistant.weekday import Weekday


def _meeting_day_name(meeting: ScheduledMeeting) -> str | None:
    placement = meeting.placement
    if isinstance(placement, WeeklyPatternPlacement):
        return placement.weekday.value
    if isinstance(placement, OccurrencePlacement):
        return list(Weekday)[placement.date.weekday()].value
    return None


def instructor_preference_issues_from_meetings(
    meetings: list[ScheduledMeeting],
    instructors: InstructorConfig,
    term: TermConfig,
) -> list[InstructorBannedSlotIssue | InstructorPreferenceIssue]:
    banned, discouraged = resolve_preference_grids(instructors.instructors, term)
    if not banned and not discouraged:
        return []

    issues: list[InstructorBannedSlotIssue | InstructorPreferenceIssue] = []

    for meeting in meetings:
        day_name = _meeting_day_name(meeting)
        if day_name is None:
            continue
        cell = meeting_day_slot_cell(day_name, meeting.start_time, term)
        if cell is None:
            continue
        for instructor_id in meeting_instructor_ids(meeting.instructor):
            if instructor_id in banned and cell in banned[instructor_id]:
                issue = InstructorBannedSlotIssue(
                    issue_type=IssueTypeEnum.INSTRUCTOR_BANNED_SLOT,
                    instructor_id=instructor_id,
                    weekday=Weekday(day_name),
                    start_time=meeting.start_time,
                    meeting=meeting,
                )
                attach_issue_text(issue)
                issues.append(issue)
                continue
            weights = discouraged.get(instructor_id)
            if weights is None:
                continue
            weight = weights.get(cell)
            if weight is None or weight <= 0:
                continue
            issue = InstructorPreferenceIssue(
                issue_type=IssueTypeEnum.INSTRUCTOR_PREFERENCE,
                instructor_id=instructor_id,
                weekday=Weekday(day_name),
                start_time=meeting.start_time,
                penalty_weight=weight,
                meeting=meeting,
            )
            attach_issue_text(issue)
            issues.append(issue)

    return issues
