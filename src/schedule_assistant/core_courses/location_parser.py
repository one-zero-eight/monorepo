"""
This file should be synced between:
https://github.com/one-zero-eight/parsers/blob/main/src/core_courses/location_parser.py
https://github.com/one-zero-eight/schedule-builder-backend/blob/main/src/core_courses/location_parser.py
"""

import re
from datetime import date, datetime, time
from functools import partial

from pydantic import BaseModel, ConfigDict


class Item(BaseModel):
    """
    Represents a parsed location string with optional modifiers and nested locations.

    This class is the result of parsing location strings from spreadsheet cells (third row
    in CoreCourseCell). The location string can contain room numbers, online indicators,
    and various temporal modifiers that affect when and where events occur.

    ## Flow Overview

    ### 1. Input: Spreadsheet Location String
    Location strings come from the third cell value in CoreCourseCell (value[2]).
    Examples:
    - "313" → simple room number
    - "ONLINE" → online event
    - "313 (WEEK 1-3) / ONLINE" → room 313 for weeks 1-3, then online
    - "ONLINE ON 13/09, 108 ON 01/11 (STARTS AT 9:00)" → online on 13/09, room 108 on 01/11, both starting at 9:00
    - "460 EXCEPT 28/11" → room 460, excluding 28/11

    ### 2. Parsing: parse_location_string()
    The location string is normalized (uppercased, "AND" replaced with commas) and parsed
    into an Item object. The parser recognizes:

    **Locations:**
    - Room numbers: "313", "room 107", "ROOM #107" → location="313" or "107"
    - Online: "ONLINE", "ОНЛАЙН", "ONLINE (TBA)" → location="ONLINE" or "ОНЛАЙН"
    - Unknown: "?" → location="?"
    - Multiple: "106/313/314" → location="106/313/314"

    **Modifiers:**
    - `starts_from`: "STARTS FROM 21/09" → starts_from=date(2024, 9, 21)
    - `ends_on`: "ENDS ON 12/03" or "ДО 12/03" or "КОНЕЦ 12/03" → ends_on=date(2024, 3, 12)
    - `starts_at`: "STARTS AT 18:00" → starts_at=time(18, 0)
    - `till`: "TILL 21:00" → till=time(21, 0)
    - `on_weeks`: "WEEK 1-3" → on_weeks=[1, 2, 3]
    - `on`: "ON 13/09, 20/09" → on=[date(2024, 9, 13), date(2024, 9, 20)]
    - `except_`: "EXCEPT 30/01, 06/02" → except_=[date(2024, 1, 30), date(2024, 2, 6)]

    **Nested Structures (NEST):**
    Complex patterns create nested Items:
    - "313 (WEEK 1-3) / ONLINE" → Item(location="313", on_weeks=[1,2,3], NEST=[Item(location="ONLINE")])
    - "105 ON 15/10, 106 ON 29/10" → Item(location="105", on=[...], NEST=[Item(location="106", on=[...])])
    - "ONLINE ON 13/09, 108 ON 01/11 (STARTS AT 9:00)" → Item with nested items sharing starts_at

    ### 3. Output: ICS Calendar Events (generate_vevents())
    The Item is converted to one or more ICS calendar events:

    **Simple Case (no location_item):**
    - Creates one recurring event with RRULE (weekly recurrence)
    - Uses event.location, event.start_time, event.end_time

    **With location_item:**

    **Base Event Properties:**
    - `location`: Uses location_item.location or falls back to event.location
    - `starts`: Uses location_item.starts_from or falls back to event.starts
    - `ends`: Uses location_item.ends_on or falls back to event.ends
    - `start_time`: Adjusted if location_item.starts_at exists (keeps duration)
    - `end_time`: Set to location_item.till if exists, otherwise calculated from start_time + duration

    **Recurrence Handling:**
    - `on_weeks` → Converted to specific dates using nearest_weekday() + weeks offset, merged into `on`
    - If `on` exists: Creates events with RDATE (specific dates) instead of RRULE
      - Each date in `on` becomes a recurrence date
      - dtstart/dtend adapted to first date in `on`
    - If `on` is None: Creates weekly recurring event with RRULE
    - If `except_` exists: Adds EXDATE to exclude specific dates from recurrence

    **Nested Items (NEST):**
    Nested items create additional calendar events:

    - If parent has RRULE (weekly recurrence):
      - For each nested item with `on` dates:
        - Creates RECURRENCE-ID events overriding specific recurrence instances
        - Uses nested item's location, starts_at, till if specified
        - Removes RRULE from override event
        - Parent event still yields with RRULE

    - If parent has RDATE (specific dates):
      - Creates separate events for nested items
      - Each nested item gets its own RDATE with its `on` dates
      - Uses nested item's location, starts_at, till if specified
      - Parent event yields first, then nested events

    **Examples of ICS Output:**

    Input: "313"
    → One event: location="313", RRULE=FREQ=WEEKLY

    Input: "ONLINE ON 13/09, 20/09"
    → One event: location="ONLINE", RDATE=[2024-09-13, 2024-09-20]

    Input: "313 (WEEK 1-3) / ONLINE"
    → Two events:
      1. location="313", RRULE=FREQ=WEEKLY (with EXDATE for weeks after 3)
      2. location="ONLINE", RDATE=[dates for weeks 4+]

    Input: "ONLINE ON 13/09, 108 ON 01/11 (STARTS AT 9:00)"
    → Three events:
      1. location="ONLINE", RDATE=[2024-09-13], dtstart=09:00
      2. location="108", RDATE=[2024-11-01], dtstart=09:00
      3. Parent recurring event (if applicable)

    Input: "460 EXCEPT 28/11"
    → One event: location="460", RRULE=FREQ=WEEKLY, EXDATE=[2024-11-28]
    """

    location: str | None = None
    'Room number, "ONLINE", "ОНЛАЙН", "?", or slash-separated combinations like "106/313"'
    starts_from: date | None = None
    "Date when the event starts (overrides event.starts)"
    ends_on: date | None = None
    "Date when the event ends (overrides event.ends)"
    starts_at: time | None = None
    "Time when the event starts (overrides event.start_time, preserves duration)"
    till: time | None = None
    "Time when the event ends (overrides event.end_time)"
    on_weeks: list[int] | None = None
    "List of week numbers (1-based, converted to dates during ICS generation)"
    on: list[date] | None = None
    "List of specific dates when event occurs (creates RDATE instead of RRULE)"
    except_: list[date] | None = None
    "List of dates to exclude from recurrence (creates EXDATE)"
    NEST: list[Item] | None = None
    "List of nested Item objects for complex location patterns"
    model_config = ConfigDict(arbitrary_types_allowed=True, use_attribute_docstrings=True)

    def describe_calendar_behavior(self, include_summary: bool = True) -> str:
        """
        Generate a human-readable description of how this Item will be converted to calendar events.

        Describes the location, recurrence patterns, time overrides, exclusions, and nested overrides.
        This method explains exactly how the Item will appear in the output ICS calendar.

        :param include_summary: Whether to include the summary at the end (set to False for nested items)
        :return: Human-readable description of calendar behavior
        """
        parts = []

        # Location
        if self.location:
            parts.append(f"Location: {self.location}")
        else:
            parts.append("Location: (inherited from event)")

        # Start date override
        if self.starts_from:
            parts.append(f"Starts from: {self.starts_from.strftime('%d/%m/%Y')}")
        if self.ends_on:
            parts.append(f"Ends on: {self.ends_on.strftime('%d/%m/%Y')}")

        # Time overrides
        time_parts = []
        if self.starts_at:
            time_parts.append(f"starts at {self.starts_at.strftime('%H:%M')}")
        if self.till:
            time_parts.append(f"ends at {self.till.strftime('%H:%M')}")
        if time_parts:
            parts.append(f"Time: {', '.join(time_parts)}")

        # Recurrence pattern
        if self.on:
            dates_str = ", ".join(d.strftime("%d/%m/%Y") for d in sorted(self.on))
            parts.append(f"Occurs on specific dates: {dates_str}")
            recurrence_type = "RDATE (specific dates only)"
        elif self.on_weeks:
            weeks_str = ", ".join(str(w) for w in sorted(self.on_weeks))
            parts.append(f"Occurs on weeks: {weeks_str} (will be converted to specific dates during ICS generation)")
            recurrence_type = "RDATE (converted from weeks)"
        else:
            recurrence_type = "RRULE (weekly recurrence)"
            parts.append("Occurs: Every week (weekly recurrence)")

        # Exclusions
        if self.except_:
            except_dates = ", ".join(d.strftime("%d/%m/%Y") for d in sorted(self.except_))
            parts.append(f"Excluded dates: {except_dates} (EXDATE - these dates will be excluded from recurrence)")

        # Nested items
        if self.NEST:
            nested_with_dates = [n for n in self.NEST if n.on]
            nested_without_dates = [n for n in self.NEST if not n.on]

            if nested_with_dates:
                parts.append(f"\nNested overrides ({len(nested_with_dates)} with specific dates):")
                for i, nested in enumerate(nested_with_dates, 1):
                    nested_desc = nested.describe_calendar_behavior(include_summary=False)
                    # Indent nested descriptions
                    nested_lines = nested_desc.split("\n")
                    indented = "\n".join(f"    {line}" for line in nested_lines)
                    parts.append(f"  Override {i}:\n{indented}")

            if nested_without_dates:
                parts.append(f"\nNested items without dates ({len(nested_without_dates)}):")
                for i, nested in enumerate(nested_without_dates, 1):
                    nested_desc = nested.describe_calendar_behavior(include_summary=False)
                    nested_lines = nested_desc.split("\n")
                    indented = "\n".join(f"    {line}" for line in nested_lines)
                    parts.append(f"  Item {i}:\n{indented}")
                parts.append("  Note: These nested items are not yet fully implemented in ICS generation")

            # Explain how nested items work
            if self.on or self.on_weeks:
                parts.append(
                    "\nCalendar behavior: Parent event uses RDATE (specific dates). "
                    "Nested items create separate calendar events with their own RDATE lists."
                )
            else:
                parts.append(
                    "\nCalendar behavior: Parent event uses RRULE (weekly recurrence). "
                    "Nested items create RECURRENCE-ID override events that replace specific "
                    "instances of the weekly recurrence with different locations/times."
                )

        result = "\n".join(parts)

        # Summary (only for top-level)
        if include_summary:
            summary_parts = [f"Calendar event type: {recurrence_type}"]
            if self.NEST:
                nested_count = len([n for n in self.NEST if n.on]) if self.NEST else 0
                if nested_count > 0:
                    summary_parts.append(f"Total events: 1 base + {nested_count} nested = {1 + nested_count} events")
                else:
                    summary_parts.append(f"Total events: 1 base event (+ {len(self.NEST)} nested items without dates)")
            else:
                summary_parts.append("Total events: 1 event")

            result += "\n\n" + " | ".join(summary_parts)

        return result


Item.model_rebuild()
ydate = partial(date, year=datetime.today().year)


def parse_location_string(x: str, from_parent: bool = False) -> Item | None:
    x = x.upper()
    x = x.replace("(ONLINE)", r"ONLINE")
    x = x.replace("(ОНЛАЙН)", r"ОНЛАЙН")
    x = x.strip()
    # replace AND with , (bounded whitespace to avoid ReDoS)
    x = re.sub(r"\s{1,32}AND\s{1,32}", ", ", x)
    x = re.sub(r"\s{1,32}И\s{1,32}", ", ", x)

    def combine_patterns(patterns):
        return r"(" + "|".join(patterns) + r")"

    def get_location(y: str):
        if m := re.fullmatch(r"^(\d+)$", y):
            return m.group(1)

        if m := re.fullmatch(r"^\?$", y):
            return "?"

        if m := re.fullmatch(r"^ROOM\s{0,8}#?\s{0,8}(\d+)$", y):
            return m.group(1)

        if m := re.fullmatch(r"^(ONLINE|ОНЛАЙН)$", y):
            return m.group(0)

        if m := re.fullmatch(r"^(ONLINE|ОНЛАЙН)\s{0,8}\(TBA\)$", y):
            return m.group(0)

        if m := re.fullmatch(r"^((\d|ONLINE|ОНЛАЙН)+(?:\s{0,8}/\s{0,8}(\d|ONLINE|ОНЛАЙН)+)+)$", y):
            locations = m.group(1)
            locations = locations.split("/")
            locations = [location.strip() for location in locations]
            return "/".join(locations)

    _loc = combine_patterns(
        [
            r"(\d+)",
            r"\?",
            r"ROOM\s{0,8}#?\s{0,8}(\d+)",
            r"(ONLINE|ОНЛАЙН)",
            r"(ONLINE|ОНЛАЙН)\s{0,8}\(TBA\)",
            r"((\d|ONLINE|ОНЛАЙН)+(?:\s{0,8}/\s{0,8}(\d|ONLINE|ОНЛАЙН)+)+)",
        ]
    )

    def location_plus_pattern(group_name: str, pattern: str):
        return rf"(?P<location>{_loc}) \(?(?P<{group_name}>{pattern})\)?"

    if as_simple_location := get_location(y=x):
        return Item(location=as_simple_location)

    _starts_from_pattern = r"\(?(STARTS ON|STARTS FROM|FROM|С|НАЧАЛО С|СТАРТ|СТАРТ С)\s*(\d{1,2}[\/.]\d{1,2})\)?"

    def starts_from(y: str):
        if m := re.fullmatch(_starts_from_pattern, y):
            _date = m.group(2).replace(".", "/")
            day, month = _date.split(sep="/")

            return Item(starts_from=ydate(day=int(day), month=int(month)))

    _ends_on_pattern = r"\(?(ENDS ON|ДО|КОНЕЦ)\s*(\d{1,2}[\/.]\d{1,2})\)?"

    def ends_on(y: str):
        if m := re.fullmatch(_ends_on_pattern, y):
            _date = m.group(2).replace(".", "/")
            day, month = _date.split(sep="/")

            return Item(ends_on=ydate(day=int(day), month=int(month)))

    _starts_at_pattern = r"\(?(STARTS|STARTS AT|НАЧАЛО В|НАЧАЛО)\s*(\d{1,2}[:.]\d{1,2})\)?"

    def starts_at(y: str):
        if m := re.fullmatch(_starts_at_pattern, y):
            _time = m.group(2).replace(".", ":")
            hour, minute = _time.split(sep=":")

            return Item(starts_at=time(hour=int(hour), minute=int(minute)))

    _week_pattern = r"\(?WEEK\s*(?P<weeks>\d+(?:-\d+)?(?:,\s*\d+(?:-\d+)?)*)(?:\s+ONLY)?\)?"

    def week(y: str):
        if m := re.fullmatch(_week_pattern, y):
            weeks = m.group("weeks")
            weeks = weeks.split(",")
            weeks = [w.split("-") for w in weeks]
            weeks = [list(range(int(w[0]), int(w[1]) + 1)) if len(w) == 2 else [int(w[0])] for w in weeks]
            weeks = [item for sublist in weeks for item in sublist]
            return Item(on_weeks=weeks)

    # ON 13/09, 20/09
    # ONLY ON 13/09 20/09
    # ТОЛЬКО НА 13/09, 20/09
    # and etc.
    _date_component_pattern = r"(?P<day>\d{1,2})[\/.](?P<month>\d{1,2})"
    _date_component_non_capturing = r"\d{1,2}[\/.]\d{1,2}"
    _on_pattern = rf"\(?(ON|ONLY ON|НА|ТОЛЬКО НА|ТОЛЬКО)\s*(?P<dates>{_date_component_non_capturing}(?:[,\s]\s*{_date_component_non_capturing})*)\)?"

    def on(y: str):
        if m := re.fullmatch(_on_pattern, y):
            dates_str = m.group("dates")
            dates = [
                ydate(day=int(dm.group("day")), month=int(dm.group("month")))
                for dm in re.finditer(_date_component_pattern, dates_str)
            ]
            return Item(on=dates)

    _till_pattern = r"\(?TILL\s*(?P<time>\d{1,2}[:.]\d{1,2})\)?"

    def till(y: str):
        if m := re.fullmatch(_till_pattern, y):
            _time = m.group("time").replace(".", ":")
            hour, minute = _time.split(sep=":")
            return Item(till=time(hour=int(hour), minute=int(minute)))

    # EXCEPT 30/01 06/02
    # КРОМЕ 30/01, 06/02
    # и т.д.
    _except_pattern = rf"\(?(EXCEPT|КРОМЕ)\s*(?P<dates_except>{_date_component_non_capturing}(?:[,\s]+{_date_component_non_capturing})*)\)?"

    def except_(y: str):
        if m := re.fullmatch(_except_pattern, y):
            dates_str = m.group("dates_except")
            dates = [
                ydate(day=int(dm.group("day")), month=int(dm.group("month")))
                for dm in re.finditer(_date_component_pattern, dates_str)
            ]
            return Item(except_=dates)

    _mod = combine_patterns(
        [
            _starts_from_pattern,
            _ends_on_pattern,
            _starts_at_pattern,
            _week_pattern,
            _on_pattern,
            _till_pattern,
            _except_pattern,
        ]
    )

    def any_modifier(y: str):
        if m := re.fullmatch(_mod, y):
            z = m.group(0)
            if as_starts_from := starts_from(z):
                return as_starts_from
            if as_ends_on := ends_on(z):
                return as_ends_on
            if as_starts_at := starts_at(z):
                return as_starts_at
            if as_week := week(z):
                return as_week
            if as_on := on(z):
                return as_on
            if as_till := till(z):
                return as_till
            if as_except := except_(z):
                return as_except

    if as_any_modifier := any_modifier(x):
        return as_any_modifier

    if m := re.fullmatch(location_plus_pattern("any_modifier", _mod), x):
        location = get_location(m.group("location"))
        as_any_modifier = any_modifier(m.group("any_modifier"))
        as_any_modifier.location = location
        return as_any_modifier

    # replace all named groups with non-capturing groups
    _mod_noname = re.sub(r"\(\?P<[^>]+>", "(?:", _mod)
    _two_modifiers_pattern = rf"\(?(?P<first>{_mod_noname})\)?\s*\(?(?P<second>{_mod_noname})\)?"

    def two_modifiers(y: str):
        if m := re.fullmatch(_two_modifiers_pattern, y):
            z1, z2 = m.group("first"), m.group("second")
            as_z1 = any_modifier(z1)
            as_z2 = any_modifier(z2)
            if as_z1 and as_z2:
                combined = as_z1.model_dump(exclude_none=True) | as_z2.model_dump(exclude_none=True)
                return Item.model_validate(combined)

    if as_two_modifiers := two_modifiers(x):
        return as_two_modifiers

    if m := re.fullmatch(location_plus_pattern("two_modifiers", _two_modifiers_pattern), x):
        location = get_location(m.group("location"))
        as_two_modifiers = two_modifiers(m.group("two_modifiers"))
        as_two_modifiers.location = location
        return as_two_modifiers
    _three_modifiers_pattern = (
        rf"\(?(?P<first>{_mod_noname})\)?\s*\(?(?P<second>{_mod_noname})\)?\s*\(?(?P<third>{_mod_noname})\)?"
    )

    def three_modifiers(y: str):
        if m := re.fullmatch(_three_modifiers_pattern, y):
            z1, z2, z3 = m.group("first"), m.group("second"), m.group("third")
            as_z1 = any_modifier(z1)
            as_z2 = any_modifier(z2)
            as_z3 = any_modifier(z3)
            if as_z1 and as_z2 and as_z3:
                combined = (
                    as_z1.model_dump(exclude_none=True)
                    | as_z2.model_dump(exclude_none=True)
                    | as_z3.model_dump(exclude_none=True)
                )
                return Item.model_validate(combined)

    if as_three_modifiers := three_modifiers(x):
        return as_three_modifiers

    if m := re.fullmatch(location_plus_pattern("three_modifiers", _three_modifiers_pattern), x):
        location = get_location(m.group("location"))
        as_three_modifiers = three_modifiers(m.group("three_modifiers"))
        as_three_modifiers.location = location
        return as_three_modifiers

    if from_parent:  # only one nesting level
        return None

    _simple_nest_pattern = rf"(?P<location>{_loc})\s*\(?(?P<rest>.+)\)?"

    def simple_nest(y: str):
        if m := re.fullmatch(_simple_nest_pattern, y):
            location = get_location(m.group("location"))
            rest = parse_location_string(m.group("rest"), from_parent=True)
            if rest is not None:
                return Item(location=location, NEST=[rest])

    if as_simple_nest := simple_nest(x):
        return as_simple_nest

    # 313 (WEEK 1-3) / ONLINE
    __1 = rf"(?P<location>{_loc})\s*\(?(?P<modifier>{_mod_noname})\)?\s*/\s*(?P<another>.+)"

    def _1(y: str):
        if m := re.fullmatch(__1, y):
            location = get_location(m.group("location"))
            modifier = any_modifier(m.group("modifier"))
            another = parse_location_string(m.group("another"), from_parent=True)
            if modifier and another:
                modifier.location = location
                modifier.NEST = [another]
                return modifier

    if as__1 := _1(x):
        return as__1

    # 105 ON 15/10, 106 ON 29/10, ONLINE ON 05/11
    __4_3 = rf"(?P<l1>{_loc})\s*(?P<m1>{_mod_noname})\s*,\s*(?P<l2>{_loc})\s*(?P<m2>{_mod_noname})\s*,\s*(?P<l3>{_loc})\s*(?P<m3>{_mod})"
    # 105 ON 15/10, 106 ON 29/10
    __4_2 = rf"(?P<l1>{_loc})\s*(?P<m1>{_mod_noname})\s*,\s*(?P<l2>{_loc})\s*(?P<m2>{_mod_noname})"

    def _4(y: str):
        if m := re.fullmatch(__4_2, y):
            l1 = get_location(m.group("l1"))
            m1 = any_modifier(m.group("m1"))
            l2 = get_location(m.group("l2"))
            m2 = any_modifier(m.group("m2"))
            if m1 and m2:
                m1.location = l1
                m2.location = l2
                m1.NEST = [m2]
                return m1
        if m := re.fullmatch(__4_3, y):
            l1 = get_location(m.group("l1"))
            m1 = any_modifier(m.group("m1"))
            l2 = get_location(m.group("l2"))
            m2 = any_modifier(m.group("m2"))
            l3 = get_location(m.group("l3"))
            m3 = any_modifier(m.group("m3"))
            if m1 and m2 and m3:
                m1.location = l1
                m2.location = l2
                m3.location = l3
                m1.NEST = [m2, m3]
                return m1

    if as__4 := _4(x):
        return as__4

    # ONLINE ON 13/09, 108 ON 01/11 (STARTS AT 9:00)
    __2 = rf"(?P<location>{_loc})\s*\(?(?P<modifier>{_mod_noname})\)?\s*,\s*(?P<another>.+?)\s*\(?(?P<common_modifier>{_mod_noname})\)?"

    def _2(y: str):
        if m := re.fullmatch(__2, y):
            location = get_location(m.group("location"))
            modifier = any_modifier(m.group("modifier"))
            another = parse_location_string(m.group("another"), from_parent=True)
            common_modifier = any_modifier(m.group("common_modifier"))

            if modifier and another and common_modifier:
                common_modifier.location = location
                if common_modifier.starts_at:
                    another.starts_at = common_modifier.starts_at
                if common_modifier.till:
                    another.till = common_modifier.till
                common_modifier.on = modifier.on
                common_modifier.NEST = [another]
                return common_modifier

    if as__2 := _2(x):
        return as__2

    # 314 (312 ON 12/09,19/09,26/09) 301 ON 03/10
    __3 = rf"(?P<location>{_loc})\s*\(?(?P<location2>{_loc})\s*(?P<modifier>{_mod_noname})\)?\s*(?P<another>.+)"

    def _3(y: str):
        if m := re.fullmatch(__3, y):
            location = get_location(m.group("location"))
            location2 = get_location(m.group("location2"))
            modifier = any_modifier(m.group("modifier"))
            another = parse_location_string(m.group("another"), from_parent=True)
            if modifier and another:
                modifier.location = location2
                item = Item(location=location, NEST=[modifier, another])
                return item

    if as__3 := _3(x):
        return as__3

    # 107 (106 НА 16.09, 105 НА 07.10) = loc (loc1 mod1, loc2 mod2)
    __5 = rf"(?P<loc>{_loc})\s*\((?P<loc1>{_loc})\s*(?P<mod1>{_mod_noname}),\s*(?P<loc2>{_loc})\s*(?P<mod2>{_mod_noname})\)"

    def _5(y: str):
        if m := re.fullmatch(__5, y):
            loc = get_location(m.group("loc"))
            loc1 = get_location(m.group("loc1"))
            mod1 = any_modifier(m.group("mod1"))
            loc2 = get_location(m.group("loc2"))
            mod2 = any_modifier(m.group("mod2"))
            if mod1 and mod2:
                mod1.location = loc1
                mod2.location = loc2
                return Item(location=loc, NEST=[mod1, mod2])

    if as__5 := _5(x):
        return as__5

    # 317 ON 15/02, 22/02, 15/03, 22/03, 5/04, 12/04, 19/04 (ONLINE ON 26/04)
    __6 = rf"(?P<location>{_loc})\s*(?P<modifier>{_mod_noname})\s*\((?P<location2>{_loc})\s*(?P<mod2>{_mod_noname})\)"

    def _6(y: str):
        if m := re.fullmatch(__6, y):
            loc = get_location(m.group("location"))
            mod = any_modifier(m.group("modifier"))
            loc2 = get_location(m.group("location2"))
            mod2 = any_modifier(m.group("mod2"))
            if mod and mod2:
                mod.location = loc
                mod2.location = loc2
                mod.NEST = [mod2]
                return mod

    if as__6 := _6(x):
        return as__6

    return None


def extract_room_from_location_string(x: str) -> str | None:
    """Parse a location string and return only the room, dropping all modifiers."""
    item = parse_location_string(x)
    if item is None:
        return None
    return item.location
