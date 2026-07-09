import datetime as dtm
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Literal, overload

from src.logging_ import logger
from src.schedule_assistant.modules.bookings.client import BookingDTO, booking_client
from src.schedule_assistant.modules.issues.booking_match import (
    booking_as_dict,
    detect_payload_conflicts,
    slot_has_matching_booking,
)
from src.schedule_assistant.modules.issues.booking_slots import build_bookable_slots
from src.schedule_assistant.modules.issues.issue_text import attach_issue_text
from src.schedule_assistant.modules.issues.meetings import meeting_instructor_ids
from src.schedule_assistant.modules.issues.placement import meeting_sort_key, meetings_overlap
from src.schedule_assistant.modules.issues.schemas import (
    CapacityIssue,
    GroupIssue,
    Issue,
    IssueTypeEnum,
    OutlookIssue,
    RoomIssue,
    ScheduledMeeting,
    StudentIssue,
    TeacherIssue,
    UnbookedIssue,
)
from src.schedule_assistant.modules.schedule_config.schemas import CoursesConfig, SectionsConfig, TermConfig
from src.schedule_assistant.utcnow import utcnow

from .graph import UndirectedGraph


@dataclass(frozen=True)
class BookingSnapshot:
    auto_bookings: tuple[dict[str, Any], ...]
    existing_bookings: tuple[BookingDTO, ...]

    @property
    def existing_dicts(self) -> list[dict[str, Any]]:
        return [booking_as_dict(booking) for booking in self.existing_bookings]


class IssueChecker:
    def __init__(
        self,
        *,
        courses: CoursesConfig,
        sections: SectionsConfig,
        term: TermConfig,
        room_to_capacity: dict[str, int | None] | None = None,
        group_to_studying_teachers: dict[str, list[str]] | None = None,
        valid_room_ids: set[str] | None = None,
    ) -> None:
        self.courses = courses
        self.sections = sections
        self.term = term
        self.room_to_capacity = room_to_capacity or {}
        self.group_to_studying_teachers = group_to_studying_teachers or {}
        self.valid_room_ids = valid_room_ids or set(self.room_to_capacity)

    @staticmethod
    def check_times_intersect(
        start_a: dtm.time,
        end_a: dtm.time,
        start_b: dtm.time,
        end_b: dtm.time,
    ) -> bool:
        _today = dtm.date.today()
        as_datetime_start_a = dtm.datetime.combine(_today, start_a)
        as_datetime_end_a = dtm.datetime.combine(_today, end_a)
        as_datetime_start_b = dtm.datetime.combine(_today, start_b)
        as_datetime_end_b = dtm.datetime.combine(_today, end_b)
        return IssueChecker.check_datetimes_intersect(
            as_datetime_start_a,
            as_datetime_end_a,
            as_datetime_start_b,
            as_datetime_end_b,
        )

    @staticmethod
    def check_datetimes_intersect(
        start_a: dtm.datetime,
        end_a: dtm.datetime,
        start_b: dtm.datetime,
        end_b: dtm.datetime,
    ) -> bool:
        return bool(start_a <= start_b <= end_a or start_b <= start_a <= end_b)

    @staticmethod
    def _instructor_key_set(instructor: str | list[str] | None) -> frozenset[str]:
        return frozenset(value.strip().lower() for value in meeting_instructor_ids(instructor))

    @staticmethod
    def _is_same_logical_meeting(meeting1: ScheduledMeeting, meeting2: ScheduledMeeting) -> bool:
        if meeting1.course_name.strip().lower() != meeting2.course_name.strip().lower():
            return False
        if (meeting1.room or "").strip().lower() != (meeting2.room or "").strip().lower():
            return False
        if IssueChecker._instructor_key_set(meeting1.instructor) != IssueChecker._instructor_key_set(
            meeting2.instructor,
        ):
            return False
        return meetings_overlap(meeting1, meeting2)

    @staticmethod
    def is_online_room(room: str | None) -> bool:
        if room is None:
            return False
        return room == "ONLINE"

    def check_for_room_issue(self, meetings: list[ScheduledMeeting]) -> list[RoomIssue]:
        room_to_slots: dict[str, list[tuple[int, ScheduledMeeting]]] = defaultdict(list)

        for index, meeting in enumerate(meetings):
            if self.is_online_room(meeting.room) or meeting.room is None:
                continue
            room_to_slots[meeting.room].append((index, meeting))

        return self._overlap_issues_for_slots(meetings, room_to_slots, key_field="room")

    @overload
    def _overlap_issues_for_slots(
        self,
        meetings: list[ScheduledMeeting],
        slots_by_key: dict[str, list[tuple[int, ScheduledMeeting]]],
        *,
        key_field: Literal["room"],
    ) -> list[RoomIssue]: ...

    @overload
    def _overlap_issues_for_slots(
        self,
        meetings: list[ScheduledMeeting],
        slots_by_key: dict[str, list[tuple[int, ScheduledMeeting]]],
        *,
        key_field: Literal["group"],
    ) -> list[GroupIssue]: ...

    def _overlap_issues_for_slots(
        self,
        meetings: list[ScheduledMeeting],
        slots_by_key: dict[str, list[tuple[int, ScheduledMeeting]]],
        *,
        key_field: Literal["group", "room"],
    ) -> list[GroupIssue] | list[RoomIssue]:
        graph = UndirectedGraph(len(meetings))
        key_by_edge: dict[tuple[int, int], str] = {}

        for key, key_meetings in slots_by_key.items():
            if len(key_meetings) == 1:
                continue

            for i, (ind1, meeting1) in enumerate(key_meetings):
                if meeting1.course_name == "Elective course on Physical Education":
                    continue
                for j in range(i + 1, len(key_meetings)):
                    ind2, meeting2 = key_meetings[j]
                    if meeting2.course_name == "Elective course on Physical Education":
                        continue
                    if meeting1 is meeting2:
                        continue
                    if self._is_same_logical_meeting(meeting1, meeting2):
                        continue
                    if meetings_overlap(meeting1, meeting2):
                        graph.add_edge(ind1, ind2)
                        key_by_edge[(min(ind1, ind2), max(ind1, ind2))] = key

        connected_components = graph.get_connected_components()
        meeting_groups = graph.get_multi_vertex_groups(meetings, connected_components)
        room_issues: list[RoomIssue] = []
        group_issues: list[GroupIssue] = []

        for meeting_group in meeting_groups:
            conflicting_keys: set[str] = set()
            for i, meeting1 in enumerate(meeting_group):
                for meeting2 in meeting_group[i + 1 :]:
                    meeting1_idx = meetings.index(meeting1)
                    meeting2_idx = meetings.index(meeting2)
                    edge_key = (min(meeting1_idx, meeting2_idx), max(meeting1_idx, meeting2_idx))
                    if edge_key in key_by_edge:
                        conflicting_keys.add(key_by_edge[edge_key])

            if not conflicting_keys:
                continue

            conflict_key = sorted(conflicting_keys)[0]
            if key_field == "group":
                issue = GroupIssue(
                    issue_type=IssueTypeEnum.GROUP,
                    group=conflict_key,
                    meetings=meeting_group,
                )
                attach_issue_text(issue)
                group_issues.append(issue)
            else:
                issue = RoomIssue(
                    issue_type=IssueTypeEnum.ROOM,
                    room=conflict_key,
                    meetings=meeting_group,
                )
                attach_issue_text(issue)
                room_issues.append(issue)

        if key_field == "group":
            return group_issues
        return room_issues

    def check_for_group_issue(self, meetings: list[ScheduledMeeting]) -> list[GroupIssue]:
        group_to_slots: dict[str, list[tuple[int, ScheduledMeeting]]] = defaultdict(list)

        for index, meeting in enumerate(meetings):
            for group in meeting.groups:
                group_to_slots[group].append((index, meeting))

        return self._overlap_issues_for_slots(meetings, group_to_slots, key_field="group")

    def _group_students_map(self) -> dict[str, set[str]]:
        return {
            group.code: {student for student in group.students}
            for group in self.sections.students_groups
            if group.students
        }

    def check_for_student_issue(self, meetings: list[ScheduledMeeting]) -> list[StudentIssue]:
        group_students = self._group_students_map()
        if not group_students:
            return []

        student_groups: dict[str, set[str]] = defaultdict(set)
        for group_code, students in group_students.items():
            for student in students:
                student_groups[student].add(group_code)

        shared_students = {student for student, groups in student_groups.items() if len(groups) > 1}
        if not shared_students:
            return []

        student_to_slots: dict[str, list[tuple[int, ScheduledMeeting]]] = defaultdict(list)
        for index, meeting in enumerate(meetings):
            meeting_students: set[str] = set()
            for group in meeting.groups:
                meeting_students.update(group_students.get(group, set()))
            for student in meeting_students:
                if student in shared_students:
                    student_to_slots[student].append((index, meeting))

        graph = UndirectedGraph(len(meetings))
        student_by_edge: dict[tuple[int, int], str] = {}

        for student, student_meetings in student_to_slots.items():
            if len(student_meetings) == 1:
                continue

            for i, (ind1, meeting1) in enumerate(student_meetings):
                if meeting1.course_name == "Elective course on Physical Education":
                    continue
                for j in range(i + 1, len(student_meetings)):
                    ind2, meeting2 = student_meetings[j]
                    if meeting2.course_name == "Elective course on Physical Education":
                        continue
                    if meeting1 is meeting2:
                        continue
                    if self._is_same_logical_meeting(meeting1, meeting2):
                        continue
                    if meetings_overlap(meeting1, meeting2):
                        graph.add_edge(ind1, ind2)
                        student_by_edge[(min(ind1, ind2), max(ind1, ind2))] = student

        connected_components = graph.get_connected_components()
        meeting_groups = graph.get_multi_vertex_groups(meetings, connected_components)
        student_issues: list[StudentIssue] = []

        for meeting_group in meeting_groups:
            conflicting_students: set[str] = set()
            for i, meeting1 in enumerate(meeting_group):
                for meeting2 in meeting_group[i + 1 :]:
                    meeting1_idx = meetings.index(meeting1)
                    meeting2_idx = meetings.index(meeting2)
                    edge_key = (min(meeting1_idx, meeting2_idx), max(meeting1_idx, meeting2_idx))
                    if edge_key in student_by_edge:
                        conflicting_students.add(student_by_edge[edge_key])

            if not conflicting_students:
                continue

            student_issue = StudentIssue(
                issue_type=IssueTypeEnum.STUDENT,
                student=sorted(conflicting_students)[0],
                meetings=meeting_group,
            )
            attach_issue_text(student_issue)
            student_issues.append(student_issue)

        return student_issues

    def check_for_teacher_issue(self, meetings: list[ScheduledMeeting]) -> list[TeacherIssue]:
        class InstructorOccupation:
            def __init__(self) -> None:
                self.teaching_meetings: list[ScheduledMeeting] = []
                self.studying_meetings: list[ScheduledMeeting] = []

        occupancies: dict[str, InstructorOccupation] = defaultdict(InstructorOccupation)

        for meeting in meetings:
            for instructor_id in meeting_instructor_ids(meeting.instructor):
                instructor_key = instructor_id.lower().strip()
                occupancies[instructor_key].teaching_meetings.append(meeting)

        for meeting in meetings:
            for group_code in meeting.groups:
                for instructor_id in self.group_to_studying_teachers.get(group_code, []):
                    instructor_key = instructor_id.lower().strip()
                    occupancies[instructor_key].studying_meetings.append(meeting)

        teacher_issues = []

        for instructor, occupation in occupancies.items():
            occupation_meetings = occupation.teaching_meetings + occupation.studying_meetings

            graph = UndirectedGraph(len(occupation_meetings))
            for i, meeting1 in enumerate(occupation_meetings):
                for j in range(i + 1, len(occupation_meetings)):
                    meeting2 = occupation_meetings[j]
                    if self._is_same_logical_meeting(meeting1, meeting2):
                        continue
                    if meetings_overlap(meeting1, meeting2):
                        graph.add_edge(i, j)

            connected_components = graph.get_connected_components()
            index_groups = graph.get_multi_vertex_groups(list(range(len(occupation_meetings))), connected_components)

            for indices_group in index_groups:
                teaching_meetings = []
                studying_meetings = []
                for i in indices_group:
                    if i < len(occupation.teaching_meetings):
                        teaching_meetings.append(occupation.teaching_meetings[i])
                    else:
                        studying_meetings.append(occupation.studying_meetings[i - len(occupation.teaching_meetings)])

                teacher_issue = TeacherIssue(
                    issue_type=IssueTypeEnum.TEACHER,
                    instructor=instructor,
                    teaching_meetings=teaching_meetings,
                    studying_meetings=studying_meetings,
                )
                attach_issue_text(teacher_issue)
                teacher_issues.append(teacher_issue)

        return teacher_issues

    def check_for_capacity_issue(self, meetings: list[ScheduledMeeting]) -> list[CapacityIssue]:
        result = []
        for meeting in meetings:
            if self.is_online_room(meeting.room) or meeting.room is None:
                continue
            capacity = self.room_to_capacity.get(meeting.room)
            if capacity is None:
                logger.warning(f"Room {meeting.room} has no capacity")
                continue
            if meeting.students_number is None:
                logger.info(f"Meeting {meeting.course_name} has no students number")
                continue

            if capacity < meeting.students_number:
                capacity_issue = CapacityIssue(
                    issue_type=IssueTypeEnum.CAPACITY,
                    room=meeting.room,
                    room_capacity=capacity,
                    needed_capacity=meeting.students_number,
                    meeting=meeting,
                )
                attach_issue_text(capacity_issue)
                result.append(capacity_issue)
        return result

    async def _load_booking_snapshot(
        self,
        *,
        start_date: dtm.date,
        end_date: dtm.date,
    ) -> BookingSnapshot:
        tz = dtm.timezone(dtm.timedelta(hours=3))
        min_needed_time = dtm.datetime.combine(start_date, dtm.time.min).replace(tzinfo=tz)
        max_needed_time = dtm.datetime.combine(end_date, dtm.time.max).replace(tzinfo=tz)

        existing_bookings = await booking_client.get_all_bookings(
            start=min_needed_time,
            end=max_needed_time,
        )
        auto_bookings = [
            booking_as_dict(booking)
            for booking in await booking_client.get_auto_bookings(
                start=min_needed_time,
                end=max_needed_time,
            )
        ]

        return BookingSnapshot(
            auto_bookings=tuple(auto_bookings),
            existing_bookings=tuple(existing_bookings),
        )

    def _bookable_slots(self) -> list:
        return build_bookable_slots(
            self.courses,
            self.sections,
            self.term,
            self.valid_room_ids,
        )

    def check_for_unbooked_issue(self, *, bookings: BookingSnapshot) -> list[UnbookedIssue]:
        issues: list[UnbookedIssue] = []

        for slot in self._bookable_slots():
            if not slot.bookable:
                continue
            if slot_has_matching_booking(
                slot.payload,
                auto_bookings=list(bookings.auto_bookings),
                existing_bookings=bookings.existing_dicts,
            ):
                continue
            issue = UnbookedIssue(
                issue_type=IssueTypeEnum.UNBOOKED,
                meeting=slot.meeting,
            )
            attach_issue_text(issue)
            issues.append(issue)

        return issues

    def check_for_outlook_issue(self, *, bookings: BookingSnapshot) -> list[OutlookIssue]:
        existing_bookings = list(bookings.existing_bookings)
        results = defaultdict(
            lambda: OutlookIssue(
                issue_type=IssueTypeEnum.OUTLOOK,
                outlook_event_title="",
                meetings=[],
                outlook_info=[],
            )
        )

        for slot in self._bookable_slots():
            if not slot.bookable:
                continue
            for _start, _end, conflicts in detect_payload_conflicts(slot.payload, existing_bookings):
                future_conflicts = [booking for booking in conflicts if booking.end_time >= utcnow()]
                if not future_conflicts:
                    continue
                for booking in future_conflicts:
                    normalized_title = booking.title.lower().strip()
                    results[normalized_title].outlook_event_title = booking.title.strip()
                    results[normalized_title].meetings.append(slot.meeting)
                    results[normalized_title].outlook_info.append(booking)

        for outlook_issue in results.values():
            visited_meetings: set[int] = set()
            deduped_meetings = []
            for meeting in outlook_issue.meetings:
                meeting_key = id(meeting)
                if meeting_key in visited_meetings:
                    continue
                visited_meetings.add(meeting_key)
                deduped_meetings.append(meeting)
            outlook_issue.meetings = sorted(deduped_meetings, key=meeting_sort_key)

            visited_bookings: set[int] = set()
            deduped_bookings = []
            for booking in outlook_issue.outlook_info:
                booking_key = id(booking)
                if booking_key in visited_bookings:
                    continue
                visited_bookings.add(booking_key)
                deduped_bookings.append(booking)
            outlook_issue.outlook_info = sorted(deduped_bookings, key=lambda item: (item.start_time, item.room_id))
            attach_issue_text(outlook_issue)

        return list(results.values())

    async def get_issues(
        self,
        meetings: list[ScheduledMeeting],
        *,
        start_date: dtm.date,
        end_date: dtm.date,
        check_room: bool = True,
        check_teacher: bool = True,
        check_capacity: bool = True,
        check_group: bool = True,
        check_student: bool = True,
        check_outlook: bool = False,
        check_unbooked: bool = True,
    ) -> list[Issue]:
        logger.info(f"{len(meetings)} meetings")
        issues: list[Issue] = []

        if check_room:
            room_issues = self.check_for_room_issue(meetings)
            logger.info(f"Found {len(room_issues)} room issues")
            issues.extend(room_issues)
        if check_teacher:
            teacher_issues = self.check_for_teacher_issue(meetings)
            logger.info(f"Found {len(teacher_issues)} teacher issues")
            issues.extend(teacher_issues)
        if check_capacity:
            capacity_issues = self.check_for_capacity_issue(meetings)
            logger.info(f"Found {len(capacity_issues)} capacity issues")
            issues.extend(capacity_issues)
        if check_group:
            group_issues = self.check_for_group_issue(meetings)
            logger.info(f"Found {len(group_issues)} group issues")
            issues.extend(group_issues)
        if check_student:
            student_issues = self.check_for_student_issue(meetings)
            logger.info(f"Found {len(student_issues)} student issues")
            issues.extend(student_issues)
        booking_snapshot: BookingSnapshot | None = None
        if check_unbooked or check_outlook:
            booking_snapshot = await self._load_booking_snapshot(start_date=start_date, end_date=end_date)
        if check_unbooked and booking_snapshot is not None:
            unbooked_issues = self.check_for_unbooked_issue(bookings=booking_snapshot)
            logger.info(f"Found {len(unbooked_issues)} unbooked issues")
            issues.extend(unbooked_issues)
        if check_outlook and booking_snapshot is not None:
            outlook_issues = self.check_for_outlook_issue(bookings=booking_snapshot)
            logger.info(f"Found {len(outlook_issues)} outlook issues")
            issues.extend(outlook_issues)

        logger.info(f"Found {len(issues)} checker issues")
        return issues
