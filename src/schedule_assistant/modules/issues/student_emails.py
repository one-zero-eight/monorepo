from collections import defaultdict

from src.schedule_assistant.modules.issues.issue_text import attach_issue_text
from src.schedule_assistant.modules.issues.schemas import IssueTypeEnum, StudentEmailIssue
from src.schedule_assistant.modules.schedule_config.schemas import SectionsConfig

_ALLOWED_STUDENT_EMAIL_SUFFIXES = ("@innopolis.ru", "@innopolis.university")


def is_valid_student_email(email: str) -> bool:
    normalized = email.strip().lower()
    return normalized.endswith(_ALLOWED_STUDENT_EMAIL_SUFFIXES)


def student_email_issues_from_sections(sections: SectionsConfig) -> list[StudentEmailIssue]:
    groups_by_email: dict[str, set[str]] = defaultdict(set)
    for group in sections.students_groups:
        for student in group.students:
            email = student.strip()
            if not email:
                continue
            groups_by_email[email].add(group.code)

    issues: list[StudentEmailIssue] = []
    for email in sorted(groups_by_email, key=str.casefold):
        if is_valid_student_email(email):
            continue
        issue = StudentEmailIssue(
            issue_type=IssueTypeEnum.STUDENT_EMAIL,
            student_email=email,
            groups=tuple(sorted(groups_by_email[email])),
        )
        attach_issue_text(issue)
        issues.append(issue)
    return issues
