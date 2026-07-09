from src.schedule_assistant.modules.issues.issue_text import attach_issue_text
from src.schedule_assistant.modules.issues.schemas import InstructorIdIssue, IssueTypeEnum
from src.schedule_assistant.modules.schedule_config.schemas import CoursesConfig, InstructorConfig
from src.schedule_assistant.modules.schedule_config.validation import collect_course_references

_ALLOWED_INSTRUCTOR_SUFFIXES = ("@innopolis.ru", "@innopolis.university")


def is_valid_instructor_id(instructor_id: str) -> bool:
    normalized = instructor_id.strip().lower()
    return normalized.endswith(_ALLOWED_INSTRUCTOR_SUFFIXES)


def collect_instructor_ids(instructors: InstructorConfig, courses: CoursesConfig) -> set[str]:
    ids = {instructor.id for instructor in instructors.instructors}
    ids.update(collect_course_references(courses).instructor_ids)
    return ids


def instructor_id_issues_from_schedule_config(
    instructors: InstructorConfig,
    courses: CoursesConfig,
) -> list[InstructorIdIssue]:
    issues: list[InstructorIdIssue] = []
    for instructor_id in sorted(collect_instructor_ids(instructors, courses)):
        if is_valid_instructor_id(instructor_id):
            continue
        issue = InstructorIdIssue(
            issue_type=IssueTypeEnum.INSTRUCTOR_ID,
            instructor_id=instructor_id,
        )
        attach_issue_text(issue)
        issues.append(issue)
    return issues
