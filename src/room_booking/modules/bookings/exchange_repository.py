# ruff: noqa: BLE001
import asyncio
import datetime as dtm
import re
import threading
import time as tm
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TypedDict, cast

import exchangelib
import exchangelib.errors
from exchangelib.folders import Folder, SingleFolderQuerySet
from exchangelib.items.calendar_item import MeetingResponse
from exchangelib.properties import (
    EWS_ID,
    HEX_ENTRY_ID,
    AlternateId,
    AssociatedCalendarItemId,
    CalendarEvent,
    CalendarEventDetails,
    ConversationId,
    FolderId,
    StatusEvent,
)
from exchangelib.recurrence import Recurrence
from exchangelib.services.get_user_availability import FreeBusyView
from fastapi import HTTPException

import src.room_booking.modules.bookings.patch_exchangelib  # noqa
from src.inh_accounts_sdk import UserSchema
from src.logging_ import logger
from src.room_booking.config import settings
from src.room_booking.config_schema import Room
from src.room_booking.modules.bookings.caching import CacheForBookings
from src.room_booking.modules.bookings.categories import sanitize_exchange_categories
from src.room_booking.modules.bookings.recently import RecentBookings
from src.room_booking.modules.bookings.recurrence import recurrence_to_xml
from src.room_booking.modules.bookings.schemas import Attendee, Booking
from src.room_booking.modules.bookings.service import (
    calendar_item_to_booking,
    get_emails_to_attendees_index,
    get_first_room_attendee_from_emails,
    get_first_room_from_emails,
)
from src.room_booking.modules.bookings.single_flight import SingleFlight
from src.room_booking.modules.bookings.tz_utils import to_msk
from src.room_booking.modules.rooms.repository import room_repository

# Location format: "Room title (user@innopolis.university)" or "... (user@innopolis.ru)"
EMAIL_IN_LOCATION_RE = re.compile(r"\(([^)]+@(?:innopolis\.university|innopolis\.ru))\)")

MEETING_RESPONSE_ITEM_CLASS_TO_STATUS = {
    "IPM.Schedule.Meeting.Resp.Pos": "Accept",
    "IPM.Schedule.Meeting.Resp.Neg": "Decline",
    "IPM.Schedule.Meeting.Resp.Tent": "Tentative",
}

INBOX_PULL_SUBSCRIPTION_TIMEOUT_MIN = 5


@dataclass
class _RoomWait:
    room_email: str
    calendar_item: exchangelib.CalendarItem | None
    event: asyncio.Event = field(default_factory=asyncio.Event)
    result: tuple[str | None, exchangelib.CalendarItem | None, str | None] | None = None


class AccountCalendarViewArgs(TypedDict):
    start: dtm.datetime
    end: dtm.datetime


class AccountGetFreeBusyInfoArgs(TypedDict):
    rooms_ids: tuple[str, ...]
    accounts: tuple[tuple[str, str, bool], ...]
    start: dtm.datetime
    end: dtm.datetime


class ExchangeBookingRepository:
    ews_endpoint: str
    account_email: str
    account: exchangelib.Account
    subscription_id: str | None
    watermark: str | None
    last_callback_time: float | None
    _recently: RecentBookings

    def __init__(
        self,
        ews_endpoint: str,
        account_email: str,
        password: str,
        *,
        calendar_id: str | None = None,
    ):
        self.ews_endpoint = ews_endpoint
        self.account_email = account_email
        self._calendar_id = calendar_id

        config = exchangelib.Configuration(
            auth_type=exchangelib.transport.BASIC,
            service_endpoint=self.ews_endpoint,
            version=exchangelib.Version(exchangelib.version.EXCHANGE_2016),
            max_connections=5,
            credentials=exchangelib.Credentials(
                username=account_email,
                password=password,
            ),
        )
        self.account = exchangelib.Account(
            self.account_email,
            access_type=exchangelib.DELEGATE,
            config=config,
            autodiscover=False,
        )
        self._room_waits: dict[str, _RoomWait] = {}
        self._waits_lock = threading.Lock()
        self._poller_lock = asyncio.Lock()
        self._inbox_poller_task: asyncio.Task[None] | None = None
        self._inbox_pull_subscription_id: str | None = None
        self._inbox_pull_watermark: str | None = None

        self.subscription_id = None
        self.watermark = None
        self.last_callback_time = None
        self._recently = RecentBookings(settings.recently_canceled_booking_ttl_sec)

        self._cache_from_busy_info = CacheForBookings(settings.ttl_bookings_from_busy_info)
        self._cache_from_account_calendar = CacheForBookings(settings.ttl_bookings_from_account_calendar)
        self._free_busy_single_flight = SingleFlight[dict[str, list[CalendarEvent]], AccountGetFreeBusyInfoArgs]()
        self._calendar_view_single_flight = SingleFlight[list[exchangelib.CalendarItem], AccountCalendarViewArgs]()
        self._cancel_single_flight = SingleFlight[bool, str]()
        self._series_recurrence_by_uid: dict[str, str] = {}

    @property
    def calendar_id(self) -> str | None:
        return self._calendar_id

    def resolve_selected_calendar(self) -> exchangelib.folders.Calendar | None:
        if self._calendar_id is None:
            return None
        return cast(
            exchangelib.folders.Calendar | None,
            SingleFolderQuerySet(
                account=self.account,
                folder=Folder(root=self.account.root, id=self._calendar_id),
            ).resolve(),
        )

    @property
    def selected_calendar(self) -> exchangelib.folders.Calendar:
        if self._calendar_id is not None:
            calendar = self.resolve_selected_calendar()
            if calendar is None:
                raise RuntimeError("Selected calendar is not found")
            return calendar
        return self.account.calendar

    def _create_booking_description(
        self,
        *,
        room: Room,
        participant_emails: list[str],
        organizer: UserSchema | None = None,
        description: str | None = None,
        **kwargs,
    ) -> str:
        if organizer is not None:
            roles: list[str] = []
            if organizer.innopolis_info.is_staff:
                roles.append("staff")
            if organizer.innopolis_info.is_student:
                roles.append("student")
            if organizer.innopolis_info.is_college:
                roles.append("college")
            intro_line = f"Booking on request from {organizer.innopolis_info.email} ({', '.join(roles) or 'no roles'})"
        else:
            intro_line = f"Booking on request from {self.account_email}"

        footer = (
            f"{intro_line}\n"
            f"Provider: https://innohassle.ru/room-booking\n"
            f"\n"
            f"View full room schedule at https://innohassle.ru/room-booking/rooms/{room.id}"
        )
        extra = (description or "").strip()
        if extra:
            return f"{extra}\n\n{footer}"
        return footer

    def _build_calendar_item(
        self,
        *,
        room: Room,
        start: dtm.datetime,
        end: dtm.datetime,
        title: str,
        participant_emails: list[str],
        organizer: UserSchema | None = None,
        recurrence: Recurrence | None = None,
        categories: list[str] | None = None,
        description: str | None = None,
        **kwargs,
    ) -> exchangelib.CalendarItem:
        start = to_msk(start)
        end = to_msk(end)
        if organizer is not None:
            location_email = organizer.innopolis_info.email
            required_attendees = [
                room.resource_email,
                organizer.innopolis_info.email,
                *participant_emails,
            ]
        else:
            location_email = self.account_email
            required_attendees = [room.resource_email, *participant_emails]

        categories = sanitize_exchange_categories(categories)

        return exchangelib.CalendarItem(
            account=self.account,
            folder=self.selected_calendar,
            start=exchangelib.EWSDateTime.from_datetime(start),
            end=exchangelib.EWSDateTime.from_datetime(end),
            subject=title,
            body=self._create_booking_description(
                room=room,
                participant_emails=participant_emails,
                organizer=organizer,
                description=description,
                start=start,
                end=end,
                title=title,
                recurrence=recurrence,
                categories=categories,
                **kwargs,
            ),
            location=f"{room.title} ({location_email})",
            resources=[room.resource_email],
            required_attendees=required_attendees,
            recurrence=recurrence,
            categories=categories,
        )

    def _remember_series_recurrence(self, item: exchangelib.CalendarItem) -> None:
        if getattr(item, "type", None) != "RecurringMaster" or not item.uid:
            return
        xml = recurrence_to_xml(cast(Recurrence | None, item.recurrence), version=item.account.version)
        if xml:
            self._series_recurrence_by_uid[cast(str, item.uid)] = xml

    def _resolve_api_calendar_item(self, item: exchangelib.CalendarItem) -> exchangelib.CalendarItem:
        """Return the calendar item id we already have (avoid slow calendar.view scan on confirm)."""
        if getattr(item, "type", None) == "RecurringMaster" and item.uid:
            self._remember_series_recurrence(item)
        return item

    def _recurrence_xml_for_calendar_item(self, item: exchangelib.CalendarItem) -> str | None:
        xml = recurrence_to_xml(cast(Recurrence | None, item.recurrence), version=item.account.version)
        if xml is not None:
            return xml
        uid = getattr(item, "uid", None)
        if uid:
            return self._series_recurrence_by_uid.get(uid)
        return None

    def booking_from_calendar_item(
        self, item: exchangelib.CalendarItem, *, room_id: str | None = None
    ) -> Booking | None:
        return calendar_item_to_booking(
            item,
            room_id=room_id,
            recurrence_xml=self._recurrence_xml_for_calendar_item(item),
        )

    async def get_server_status(self) -> dict | None:
        try:
            t1 = tm.monotonic()
            status = {}
            status["version"] = str(self.account.version)
            calendar_folder_info = await asyncio.to_thread(lambda: self.selected_calendar)
            status["folder"] = str(calendar_folder_info)
            t2 = tm.monotonic()
            status["time_taken"] = f"{t2 - t1:.2f} seconds"
            return status
        except Exception as e:
            logger.error(f"Error getting calendar folder info: {e}")
            return None

    async def push_subscription(self, callback_url: str) -> tuple[str, str]:
        with self.selected_calendar.push_subscription(
            callback_url=callback_url,
            event_types=("ModifiedEvent",),
        ) as (
            subscription_id,
            watermark,
        ):
            self.subscription_id = subscription_id
            self.watermark = watermark
            self.last_callback_time = tm.monotonic()

            return (subscription_id, watermark)

    async def _fetch_bookings_from_busy_info(
        self,
        rooms: list[Room],
        start: dtm.datetime,
        end: dtm.datetime,
        use_cache: bool = True,
        use_dedup: bool = True,
    ) -> dict[str, list[Booking]]:
        t_start = tm.monotonic()
        rooms_ids = {room.id for room in rooms}

        # ---- Get cached bookings ----
        if use_cache:
            room_x_cached_bookings, cache_misses = await self._cache_from_busy_info.get_cached_bookings(
                rooms_ids, start, end
            )

            if not cache_misses:  # full cache hit
                logger.info(f"Cache hit for bookings from busy info for rooms {rooms_ids}")
                return room_x_cached_bookings
            else:  # TODO: request only subset of rooms that are not in cache
                logger.info(f"Cache miss for bookings from busy info for rooms: {cache_misses}")
        # ^^^^^

        # ---- Fetch account free busy info with only one request at a time ----
        rooms_ids = tuple(room.id for room in rooms)
        accounts = tuple((room.resource_email, "Resource", False) for room in rooms)
        args = AccountGetFreeBusyInfoArgs(
            rooms_ids=rooms_ids,
            accounts=accounts,
            start=to_msk(start),
            end=to_msk(end),
        )

        async def free_busy_task(args: AccountGetFreeBusyInfoArgs) -> dict[str, list[CalendarEvent]]:
            account_free_busy_info = await asyncio.to_thread(
                lambda: list(
                    self.account.protocol.get_free_busy_info(
                        accounts=args["accounts"],
                        start=exchangelib.EWSDateTime.from_datetime(args["start"]),
                        end=exchangelib.EWSDateTime.from_datetime(args["end"]),
                        requested_view="Detailed",
                    )
                ),
            )
            account_free_busy_info = cast(Iterable[FreeBusyView], account_free_busy_info)

            room_id_x_calendar_events: dict[str, list[CalendarEvent]] = {}

            for i, busy_info in enumerate(account_free_busy_info):
                room_id = args["rooms_ids"][i]
                if busy_info is not None and busy_info.calendar_events is not None:
                    room_id_x_calendar_events[room_id] = list(cast(Iterable[CalendarEvent], busy_info.calendar_events))
                else:
                    room_id_x_calendar_events[room_id] = []

            return room_id_x_calendar_events

        room_id_x_calendar_events = await self._free_busy_single_flight.run(
            args, lambda: asyncio.create_task(free_busy_task(args)), use_dedup=use_dedup
        )
        # ^^^^^

        # ---- Convert EWS CalendarEvents to ours Bookings ----
        room_id_x_bookings: dict[str, list[Booking]] = {k: [] for k in rooms_ids}
        for room_id, room_calendar_events in room_id_x_calendar_events.items():
            room = room_repository.get_by_id(room_id)

            for calendar_event in room_calendar_events:
                title = "Busy"
                email_in_location = None
                attendee = []
                outlook_entry_id = None

                if room is not None:
                    attendee.append(Attendee(email=room.resource_email, status=None, assosiated_room_id=room.id))

                if calendar_event.details is not None:
                    details = cast(CalendarEventDetails, calendar_event.details)
                    if details.subject is not None:
                        title = cast(str, details.subject)
                    if details.location is not None:
                        location = cast(str, details.location)
                        match = EMAIL_IN_LOCATION_RE.search(location)
                        if match is not None:
                            email_in_location = match.group(1)
                            attendee.append(Attendee(email=email_in_location, status=None, assosiated_room_id=None))
                    if details.id is not None:
                        outlook_entry_id = str(details.id)

                room_id_x_bookings[room_id].append(
                    Booking(
                        room_id=room_id,
                        title=title,
                        start=to_msk(cast(dtm.datetime, calendar_event.start)),
                        end=to_msk(cast(dtm.datetime, calendar_event.end)),
                        outlook_booking_id=None,
                        outlook_entry_id=outlook_entry_id,
                        attendees=attendee or None,
                        # busy info doesn't contain attendees info, we can fetch it from account calendar using outlook_entry_id. Although, we know that room is always in the attendees list, and we can parse organizer email from location.
                    )
                )
        # ^^^^^

        # ---- Cache bookings ----
        await self._cache_from_busy_info.update_cache_from_mapping(
            room_id_x_bookings=room_id_x_bookings, start=start, end=end
        )
        # ^^^^^

        logger.info(f"_fetch_bookings_from_busy_info took {tm.monotonic() - t_start:.2f}s")
        return room_id_x_bookings

    async def _fetch_bookings_from_account_calendar(
        self,
        rooms: list[Room],
        start: dtm.datetime,
        end: dtm.datetime,
        use_cache: bool = True,
        use_dedup: bool = True,
    ) -> dict[str, list[Booking]]:
        t_start = tm.monotonic()
        rooms_ids = {room.id for room in rooms}

        # ---- Get cached bookings ----
        if use_cache:
            room_x_cached_bookings, cache_misses = await self._cache_from_account_calendar.get_cached_bookings(
                rooms_ids, start, end
            )

            if not cache_misses:  # full cache hit
                logger.info(f"Cache hit for bookings from account calendar for rooms: {rooms_ids}")
                return room_x_cached_bookings
            else:  # TODO: request only subset of rooms that are not in cache
                logger.info(f"Cache miss for bookings from account calendar for rooms: {cache_misses}")
        # ^^^^^

        # ---- Fetch account calendar view with only one request at a time ----
        args = AccountCalendarViewArgs(start=to_msk(start), end=to_msk(end))

        async def calendar_view_task(args: AccountCalendarViewArgs) -> list[exchangelib.CalendarItem]:
            return await asyncio.to_thread(
                lambda: list(
                    self.selected_calendar.view(
                        exchangelib.EWSDateTime.from_datetime(args["start"]),
                        exchangelib.EWSDateTime.from_datetime(args["end"]),
                    ).only("required_attendees", "subject", "start", "end", "id")
                )
            )

        calendar_items = await self._calendar_view_single_flight.run(
            args,
            lambda: asyncio.create_task(calendar_view_task(args)),
            use_dedup=use_dedup,
        )
        # ^^^^^

        # ---- Convert EWS CalendarItems to ours Bookings ----
        room_x_bookings: dict[str, list[Booking]] = {k: [] for k in rooms_ids}
        for item in calendar_items:
            email_index = get_emails_to_attendees_index(item)
            room = get_first_room_from_emails(email_index)

            if room is None:
                continue

            if room.id not in rooms_ids:
                continue

            room_attendee = email_index.get(room.resource_email)
            if room_attendee is None or room_attendee.response_type == "Decline":
                continue

            booking = calendar_item_to_booking(item, room_id=room.id)
            if booking is not None:
                room_x_bookings[room.id].append(booking)
        # ^^^^^

        # ---- Cache bookings ----
        await self._cache_from_account_calendar.update_cache_from_mapping(
            room_id_x_bookings=room_x_bookings, start=start, end=end
        )
        # ^^^^^

        logger.info(f"_fetch_bookings_from_account_calendar took {tm.monotonic() - t_start:.2f}s")
        return room_x_bookings

    async def fetch_user_bookings(self, attendee_email: str, start: dtm.datetime, end: dtm.datetime) -> list[Booking]:
        """
        Fetch bookings from account calendar for all rooms for the given time range and filter out bookings that are not related to the user.
        """
        bookings_from_account_calendar = await self._fetch_bookings_from_account_calendar(
            rooms=room_repository.get_all(include_red=True),
            start=start,
            end=end,
            use_cache=False,  # we dont use cache, so there is no need to check recently created and updated bookings
            use_dedup=True,
        )

        user_bookings = []
        for bookings in bookings_from_account_calendar.values():
            for booking in bookings:
                if not booking.attendees:
                    continue

                accepted_by_rooms = all(
                    attendee.status != "Decline" for attendee in booking.attendees if attendee.assosiated_room_id
                )

                if not accepted_by_rooms:
                    continue

                user_attendee = next(
                    (attendee for attendee in booking.attendees if attendee.email == attendee_email), None
                )

                if user_attendee is None or user_attendee.status == "Decline":
                    continue

                user_bookings.append(booking)
        user_bookings.sort(key=lambda x: x.start, reverse=True)
        return user_bookings

    async def _fetch_bookings_both_from_account_calendar_and_busy_info(
        self, room_ids: list[str], start: dtm.datetime, end: dtm.datetime
    ) -> list[Booking]:
        rooms = room_repository.get_by_ids(room_ids)
        rooms = list(filter(None, rooms))
        if not rooms:
            return []

        t_start = tm.monotonic()
        bookings_from_account_calendar, bookings_from_busy_info = await asyncio.gather(
            self._fetch_bookings_from_account_calendar(
                rooms=rooms,
                start=start,
                end=end,
                use_cache=True,
                use_dedup=True,
            ),
            self._fetch_bookings_from_busy_info(
                rooms=rooms,
                start=start,
                end=end,
                use_cache=True,
                use_dedup=True,
            ),
        )

        account_calendar_registry = defaultdict(list)
        busy_info_registry = defaultdict(list)

        def key(booking: Booking) -> tuple[str, dtm.datetime, dtm.datetime]:
            return booking.room_id, booking.start, booking.end

        for bookings in bookings_from_account_calendar.values():
            for updated in bookings:
                account_calendar_registry[key(updated)].append(updated)
        for bookings in bookings_from_busy_info.values():
            for updated in bookings:
                busy_info_registry[key(updated)].append(updated)

        bookings = []

        for key in set(account_calendar_registry.keys()) | set(busy_info_registry.keys()):
            ac_bookings: list = account_calendar_registry[key]
            bi_bookings: list = busy_info_registry[key]
            conflicting_bookings_len = len(ac_bookings) + len(bi_bookings)

            # TODO: properly handle two sources of truth
            # We can return busy_info bookings and account bookings separately
            # with an intention that account booking info would be duplicated in busy_info.
            # busy_info would be used as source of truth for busyness of room
            # account bookings would be used as source of bookings made by service account

            if conflicting_bookings_len == 1:
                bookings.extend(ac_bookings + bi_bookings)
            elif ac_bookings:
                bookings.append(ac_bookings[0])
            else:
                bookings.extend(bi_bookings)

        # ---- Use cache for recently created, updated and canceled bookings ----
        recently_created_bookings = await self._recently.get_created()
        recently_canceled_bookings = await self._recently.get_canceled()
        recently_updated_bookings = await self._recently.get_updated_with_ts()

        for canceled_booking_id in recently_canceled_bookings:
            recently_created_bookings.pop(canceled_booking_id, None)
            recently_updated_bookings.pop(canceled_booking_id, None)

        for recently_updated_booking_id in recently_updated_bookings:
            # we will prioritize recently updated bookings over recently created bookings
            recently_created_bookings.pop(recently_updated_booking_id, None)

        bookings_with_recently = []
        for b in bookings:
            oid = b.outlook_booking_id
            if oid is not None:
                if oid in recently_canceled_bookings:
                    # we will not add recently canceled bookings to the list
                    logger.info(f"Booking {oid} skipped: recently canceled")

                elif oid in recently_updated_bookings:
                    # add updated booking to the list and remove it from the recently updated bookings, prioritizing updated bookings
                    updated_ts, updated = recently_updated_bookings.pop(oid)
                    if (t_start - settings.ttl_bookings_from_account_calendar) < updated_ts:
                        bookings_with_recently.append(updated)
                        logger.info(f"Booking {oid}: using recently updated version")
                    else:
                        bookings_with_recently.append(b)
                        logger.info(f"Booking {oid}: using fetched version")

                elif oid in recently_created_bookings:
                    # add booking to the list and remove it from the recently created bookings, prioritizing fetched bookings
                    bookings_with_recently.append(b)
                    recently_created_bookings.pop(oid)
                    logger.info(f"Booking {oid}: in fetch and recently created, using fetched")

                else:
                    # just booking from somewhere else, add the booking to the list
                    bookings_with_recently.append(b)
            else:
                bookings_with_recently.append(b)

        for created_booking in recently_created_bookings.values():
            # add remaining recently created bookings to the list, that were not updated or canceled
            if created_booking.room_id in room_ids:
                bookings_with_recently.append(created_booking)
                logger.info(f"Booking {created_booking}: remaining recently created (not in fetch), appended")

        # ^^^^^

        bookings_with_recently.sort(key=lambda x: x.start, reverse=True)

        return bookings_with_recently

    async def get_bookings_for_room(
        self,
        room_id: str,
        from_dt: dtm.datetime,
        to_dt: dtm.datetime,
    ) -> list[Booking]:
        """
        Get bookings for a specific room for the given time range.
        """
        return await self._fetch_bookings_both_from_account_calendar_and_busy_info([room_id], from_dt, to_dt)

    async def get_bookings_for_certain_rooms(
        self,
        room_ids: list[str],
        from_dt: dtm.datetime,
        to_dt: dtm.datetime,
    ) -> list[Booking]:
        """
        Get bookings for certain rooms for the given time range.
        """
        return await self._fetch_bookings_both_from_account_calendar_and_busy_info(room_ids, from_dt, to_dt)

    async def create_booking(
        self,
        room: Room,
        start: dtm.datetime,
        end: dtm.datetime,
        title: str,
        participant_emails: list[str],
        organizer: UserSchema | None = None,
        recurrence: Recurrence | None = None,
        categories: list[str] | None = None,
        description: str | None = None,
    ) -> Booking:
        """
        Create a booking for a specific room.
        May raise HTTPExceptions.
        """
        item = self._build_calendar_item(
            room=room,
            start=start,
            end=end,
            title=title,
            participant_emails=participant_emails,
            organizer=organizer,
            recurrence=recurrence,
            categories=categories,
            description=description,
        )
        await asyncio.to_thread(item.save, send_meeting_invitations=exchangelib.items.SEND_TO_ALL_AND_SAVE_COPY)
        booking, _ = await self._confirm_booking(room=room, item_id=str(item.id))
        return booking

    def _meeting_response_matches_calendar_item(
        self,
        message: MeetingResponse,
        calendar_item_id: str,
        calendar_item: exchangelib.CalendarItem | None,
    ) -> bool:
        assoc = cast(AssociatedCalendarItemId | None, message.associated_calendar_item_id)
        if assoc is not None and assoc.id == calendar_item_id:
            return True
        conversation_id = cast(ConversationId | None, message.conversation_id)
        if (
            calendar_item
            and calendar_item.conversation_id
            and conversation_id
            and conversation_id.id == cast(ConversationId, calendar_item.conversation_id).id
        ):
            return True
        if calendar_item and calendar_item.uid and assoc is not None:
            associated_item = self._fetch_calendar_item(cast(str, assoc.id))
            if associated_item is not None and associated_item.uid == calendar_item.uid:
                return True
        return False

    def _fetch_calendar_item(self, item_id: str) -> exchangelib.CalendarItem | None:
        try:
            item = self.selected_calendar.get(id=item_id)
            if isinstance(item, exchangelib.CalendarItem):
                return item
        except exchangelib.errors.ErrorItemNotFound:
            pass
        except Exception as e:
            logger.warning(f"selected_calendar.get failed for {item_id}: {e}")
        try:
            item = self.account.root.get(id=item_id)
            if isinstance(item, exchangelib.CalendarItem):
                return item
        except exchangelib.errors.ErrorItemNotFound:
            pass
        for fetched in self.account.fetch(ids=[item_id]):
            if isinstance(fetched, exchangelib.CalendarItem):
                return fetched
        return None

    @staticmethod
    def _meeting_response_text_body(message: MeetingResponse) -> str | None:
        text_body = cast(str | None, message.text_body)
        if text_body:
            text = text_body.strip()
            if text:
                return text
        body = cast(str | None, message.body)
        if body:
            return body.strip() or None
        return None

    def _meeting_response_message_body(self, message: MeetingResponse) -> str | None:
        return self._meeting_response_text_body(message)

    def _result_from_meeting_response(
        self,
        *,
        calendar_item_id: str,
        calendar_item: exchangelib.CalendarItem | None,
        room_email: str,
        message: MeetingResponse,
    ) -> tuple[str | None, exchangelib.CalendarItem | None, str | None] | None:
        if not self._meeting_response_matches_calendar_item(message, calendar_item_id, calendar_item):
            return None
        sender = cast(exchangelib.properties.Mailbox | None, message.sender)  # ty: ignore[unresolved-attribute]
        if sender and sender.email_address and cast(str, sender.email_address).lower() != room_email.lower():
            return None
        response_type = MEETING_RESPONSE_ITEM_CLASS_TO_STATUS.get(cast(str, message.item_class or ""))
        if response_type is None:
            return None
        assoc = cast(AssociatedCalendarItemId | None, message.associated_calendar_item_id)
        assoc_id = cast(str, assoc.id) if assoc else None
        fetch_id = assoc_id or calendar_item_id
        if calendar_item is not None and (assoc_id is None or assoc_id == calendar_item_id):
            resolved_item = calendar_item
        else:
            resolved_item = self._fetch_calendar_item(fetch_id)
        message_body = self._meeting_response_message_body(message)
        return response_type, resolved_item, message_body

    def _renew_inbox_pull_subscription(self) -> None:
        if self._inbox_pull_subscription_id is not None:
            try:
                self.account.inbox.unsubscribe(self._inbox_pull_subscription_id)
            except Exception:
                logger.exception(
                    f"Failed to unsubscribe from inbox pull subscription {self._inbox_pull_subscription_id}"
                )
        self._inbox_pull_subscription_id, self._inbox_pull_watermark = self.account.inbox.subscribe_to_pull(
            event_types=["NewMailEvent", "CreatedEvent"],
            watermark=self._inbox_pull_watermark,
            timeout=INBOX_PULL_SUBSCRIPTION_TIMEOUT_MIN,
        )
        logger.info(f"Inbox pull subscription created: {self._inbox_pull_subscription_id}")

    def _fetch_inbox_notifications(self) -> list:
        if self._inbox_pull_subscription_id is None or self._inbox_pull_watermark is None:
            self._renew_inbox_pull_subscription()

        def _pull() -> list:
            if self._inbox_pull_subscription_id is None:
                raise RuntimeError("Inbox pull subscription is not initialized")
            return list(
                self.account.inbox.get_events(
                    subscription_id=self._inbox_pull_subscription_id,
                    watermark=self._inbox_pull_watermark,
                )
            )

        try:
            return _pull()
        except Exception as e:
            logger.warning(f"Inbox pull get_events failed, renewing: {e}")
            self._renew_inbox_pull_subscription()
            return _pull()

    def _inbox_poll_step(self) -> None:
        notifications = self._fetch_inbox_notifications()

        with self._waits_lock:
            pending = [
                (calendar_item_id, wait)
                for calendar_item_id, wait in self._room_waits.items()
                if not wait.event.is_set()
            ]
            registered_wait_ids = set(self._room_waits.keys())

        for notification in notifications:
            batch_events = list(notification.events or [])
            item_events = [e for e in batch_events if not isinstance(e, StatusEvent)]
            if item_events:
                logger.debug(
                    f"Inbox poll {self.account_email}: events={len(batch_events)} "
                    f"item_events={len(item_events)} pending_waits={len(pending)} "
                    f"more_events={notification.more_events}"
                )
            for event in batch_events:
                if isinstance(event, StatusEvent):
                    if event.watermark:
                        self._inbox_pull_watermark = event.watermark
                    continue
                if not event.item_id:
                    continue
                event_item_id = event.item_id
                logger.debug(
                    f"Inbox event {self.account_email}: type={type(event).__name__} item_id={event_item_id.id}"
                )
                try:
                    message = self.account.inbox.get(
                        id=event_item_id.id,
                        changekey=event_item_id.changekey,
                    )
                except Exception as e:
                    logger.warning(f"Inbox pull: failed to fetch {event_item_id.id}: {e}")
                    continue
                if not isinstance(message, MeetingResponse):
                    logger.debug(
                        f"Inbox event {self.account_email}: item_id={event_item_id.id} "
                        f"item_class={message.item_class!r} (not a meeting response)"
                    )
                    continue
                sender = message.sender.email_address if message.sender else None
                logger.debug(
                    f"Inbox meeting response {self.account_email}: item_id={event_item_id.id} "
                    f"item_class={message.item_class!r} sender={sender} subject={message.subject!r}"
                )
                matched_any = False
                for calendar_item_id, wait in pending:
                    if wait.event.is_set():
                        continue
                    result = self._result_from_meeting_response(
                        calendar_item_id=calendar_item_id,
                        calendar_item=wait.calendar_item,
                        room_email=wait.room_email,
                        message=message,
                    )
                    if result is None:
                        continue
                    matched_any = True
                    wait.result = result
                    logger.info(f"Inbox matched {calendar_item_id} response={result[0]} subject={message.subject!r}")
                    wait.event.set()
                if pending and not matched_any:
                    assoc = message.associated_calendar_item_id
                    assoc_for_registered_wait = assoc is not None and assoc.id in registered_wait_ids
                    if not assoc_for_registered_wait:
                        logger.warning(
                            f"Inbox meeting response did not match {len(pending)} pending wait(s) "
                            f"{self.account_email}: assoc_calendar_item_id={assoc.id if assoc else None} "
                            f"conversation_id={message.conversation_id.id if message.conversation_id else None}"
                        )
            if batch_events and batch_events[-1].watermark:
                self._inbox_pull_watermark = batch_events[-1].watermark

    async def _inbox_poller_loop(self) -> None:
        while True:
            try:
                await asyncio.to_thread(self._inbox_poll_step)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(f"Inbox poll failed for {self.account_email}")
                self._inbox_pull_subscription_id = None
                await asyncio.sleep(1)
                continue
            await asyncio.sleep(0.05)

    async def start_inbox_poller(self) -> None:
        async with self._poller_lock:
            if self._inbox_poller_task is not None and not self._inbox_poller_task.done():
                return
            self._inbox_poller_task = asyncio.create_task(
                self._inbox_poller_loop(),
                name=f"inbox_pull:{self.account_email}",
            )
            logger.info(f"Inbox poller started for {self.account_email}")

    async def stop_inbox_poller(self) -> None:
        async with self._poller_lock:
            task = self._inbox_poller_task
            if task is None:
                return
            task.cancel()
            self._inbox_poller_task = None
        try:
            await task
        except asyncio.CancelledError:
            pass
        logger.info(f"Inbox poller stopped for {self.account_email}")

    async def _await_room_meeting_response(
        self,
        *,
        calendar_item_id: str,
        room_email: str,
        timeout_s: int = 30,
    ) -> tuple[str | None, exchangelib.CalendarItem | None, str | None]:
        wait = _RoomWait(room_email=room_email.lower(), calendar_item=None)
        with self._waits_lock:
            self._room_waits[calendar_item_id] = wait
            pending_count = len(self._room_waits)
        logger.info(
            f"Room response wait registered {self.account_email}: calendar_item_id={calendar_item_id} "
            f"room={room_email} pending_waits={pending_count} timeout_s={timeout_s}"
        )
        try:
            await asyncio.wait_for(wait.event.wait(), timeout_s)
        except TimeoutError:
            logger.warning(
                f"Room response wait timeout {self.account_email}: calendar_item_id={calendar_item_id} "
                f"room={room_email} timeout_s={timeout_s}"
            )
            return None, await asyncio.to_thread(self._fetch_calendar_item, calendar_item_id), None
        finally:
            with self._waits_lock:
                self._room_waits.pop(calendar_item_id, None)
        if wait.result is not None:
            return wait.result
        return None, await asyncio.to_thread(self._fetch_calendar_item, calendar_item_id), None

    @staticmethod
    def _room_response_error_detail(message: str, *, message_body: str | None = None) -> str | dict[str, str]:
        if message_body:
            return {"message": message, "message_body": message_body}
        return message

    async def _raise_booking_declined_by_room(
        self,
        *,
        room: Room,
        calendar_item: exchangelib.CalendarItem | None,
        message_body: str | None = None,
    ) -> None:
        if calendar_item is not None:
            await self.cancel_booking(calendar_item, email=room.resource_email)
        raise HTTPException(
            403,
            self._room_response_error_detail("Booking was declined by the room", message_body=message_body),
        )

    async def _confirm_booking(
        self,
        *,
        room: Room,
        item_id: str,
        wait_before_poll: bool = True,
        timeout_s: int = 30,
    ) -> tuple[Booking, str | None]:
        if wait_before_poll:
            await asyncio.sleep(1)

        response_type, item, message_body = await self._await_room_meeting_response(
            calendar_item_id=item_id,
            room_email=room.resource_email,
            timeout_s=timeout_s,
        )

        if item is None and response_type is not None:
            item = await asyncio.to_thread(self._fetch_calendar_item, item_id)

        if response_type == "Decline":
            await self._raise_booking_declined_by_room(room=room, calendar_item=item, message_body=message_body)

        if item is None:
            if await self.is_recently_canceled(item_id):
                await self._raise_booking_declined_by_room(room=room, calendar_item=None)
            logger.warning(
                f"Confirm failed to load calendar item after room response "
                f"{self.account_email}: item_id={item_id} response_type={response_type}"
            )
            raise HTTPException(404, "Booking was removed during booking")

        if response_type is None:
            await self.cancel_booking(item, email=room.resource_email)
            raise HTTPException(403, "Room did not accept the booking in time")

        api_item = await asyncio.to_thread(self._resolve_api_calendar_item, item)
        booking = self.booking_from_calendar_item(api_item, room_id=room.id)
        if booking is None:
            raise HTTPException(404, "Room attendee not found in booking attendees")
        await self._recently.mark_created(str(api_item.id), booking)
        return booking, message_body

    async def get_item(self, item_id: str) -> exchangelib.items.Item | None:
        try:
            return await asyncio.to_thread(self.account.root.get, id=item_id)
        except exchangelib.errors.ErrorItemNotFound:
            return None

    async def get_booking(self, item_id: str) -> exchangelib.CalendarItem | None:
        item = await self.get_item(item_id)
        if isinstance(item, exchangelib.CalendarItem):
            return item
        return None

    async def get_booking_by_entry_id(self, outlook_entry_id: str, room: Room) -> Booking | None:
        try:
            booking = await asyncio.to_thread(
                self._get_booking_by_entry_id, outlook_entry_id=outlook_entry_id, room=room
            )
            return booking
        except exchangelib.errors.ErrorItemNotFound:
            return None

    @staticmethod
    def _normalize_outlook_entry_id(outlook_entry_id: str) -> str:
        return outlook_entry_id.strip()

    def _get_calendar_item_by_entry_id(self, outlook_entry_id: str, room: Room) -> exchangelib.CalendarItem:
        outlook_entry_id = self._normalize_outlook_entry_id(outlook_entry_id)
        item_id = next(
            iter(
                self.account.protocol.convert_ids(
                    [AlternateId(id=outlook_entry_id, format=HEX_ENTRY_ID, mailbox=room.resource_email)],
                    destination_format=EWS_ID,
                )
            )
        )
        item = self.account.root.get(id=item_id.id)
        if not isinstance(item, exchangelib.CalendarItem):
            raise exchangelib.errors.ErrorItemNotFound("Not a calendar item")
        return item

    def _find_calendar_item_for_room_slot(
        self,
        room: Room,
        start: dtm.datetime,
        end: dtm.datetime,
        title: str,
    ) -> exchangelib.CalendarItem | None:
        start_msk = to_msk(start)
        end_msk = to_msk(end)
        title_normalized = title.strip()
        window_start = start_msk - dtm.timedelta(hours=2)
        window_end = end_msk + dtm.timedelta(hours=2)
        items = self.selected_calendar.view(
            exchangelib.EWSDateTime.from_datetime(window_start),
            exchangelib.EWSDateTime.from_datetime(window_end),
        ).only("required_attendees", "resources", "subject", "start", "end")
        for item in items:
            email_index = get_emails_to_attendees_index(item)
            if room.resource_email not in email_index:
                continue
            item_start = to_msk(cast(dtm.datetime, item.start))
            item_end = to_msk(cast(dtm.datetime, item.end))
            if item_start != start_msk or item_end != end_msk:
                continue
            if (cast(str, item.subject) or "").strip() != title_normalized:
                continue
            return item
        return None

    async def find_calendar_item_for_room_slot(
        self,
        room: Room,
        start: dtm.datetime,
        end: dtm.datetime,
        title: str,
    ) -> exchangelib.CalendarItem | None:
        return await asyncio.to_thread(
            self._find_calendar_item_for_room_slot,
            room,
            start,
            end,
            title,
        )

    def _get_booking_by_entry_id(self, outlook_entry_id: str, room: Room) -> Booking | None:
        calendar_item = self._get_calendar_item_by_entry_id(outlook_entry_id, room)
        from_my_calendar = cast(FolderId, calendar_item.parent_folder_id).id == self.selected_calendar.id
        return calendar_item_to_booking(
            calendar_item,
            room_id=room.id,
            was_fetched_from_room_calendar=not from_my_calendar,
            room_calendar_entry_id=outlook_entry_id,
        )

    async def get_calendar_item_by_entry_id(
        self,
        outlook_entry_id: str,
        room: Room,
    ) -> exchangelib.CalendarItem | None:
        try:
            return await asyncio.to_thread(
                self._get_calendar_item_by_entry_id,
                outlook_entry_id=outlook_entry_id,
                room=room,
            )
        except exchangelib.errors.ErrorItemNotFound:
            return None

    async def cancel_booking_by_entry_id(
        self,
        outlook_entry_id: str,
        room: Room,
        *,
        email: str | None,
    ) -> bool:
        item = await self.get_calendar_item_by_entry_id(outlook_entry_id, room)
        if item is None:
            return False
        return await self.cancel_booking(item, email=email)

    async def update_booking(
        self,
        item_id: str,
        new_start: dtm.datetime | None = None,
        new_end: dtm.datetime | None = None,
        new_title: str | None = None,
    ) -> Booking | None:
        item = await self.get_booking(item_id)
        if item is None:
            return None

        email_index = get_emails_to_attendees_index(item)
        old_room_attendee = get_first_room_attendee_from_emails(email_index)

        update_fields = []
        if new_start is not None:
            new_start = to_msk(new_start)
            item.start = exchangelib.EWSDateTime.from_datetime(new_start)
            update_fields.append("start")
        if new_end is not None:
            new_end = to_msk(new_end)
            item.end = exchangelib.EWSDateTime.from_datetime(new_end)
            update_fields.append("end")
        if new_title is not None:
            item.subject = new_title  # ty: ignore[invalid-assignment]
            update_fields.append("subject")

        if update_fields:
            await asyncio.to_thread(
                item.save,
                update_fields=update_fields,
                send_meeting_invitations=exchangelib.items.SEND_TO_ALL_AND_SAVE_COPY,
            )

        await asyncio.sleep(3)

        tries = 10
        for _ in range(tries):
            await asyncio.sleep(1)

            new_item = await self.get_booking(item_id)
            if new_item is None:
                continue
            new_email_index = get_emails_to_attendees_index(new_item)
            new_room_attendee = get_first_room_attendee_from_emails(new_email_index)

            if (
                new_room_attendee is not None
                and old_room_attendee is not None
                and new_room_attendee.last_response_time != old_room_attendee.last_response_time
            ):
                booking = calendar_item_to_booking(new_item)
                if booking is not None:
                    await self._recently.mark_updated(item_id, booking)
                return booking

        return None

    async def cancel_booking(self, item: exchangelib.CalendarItem, email: str | None) -> bool:
        item_id = str(item.id)

        if await self._recently.is_canceled(item_id):
            return True

        async def cancel_task() -> bool:
            await asyncio.to_thread(
                item.cancel,
                new_body=f"Canceled by {email}\nProvider: https://innohassle.ru/room-booking",
            )
            await self._recently.mark_canceled(item_id)
            return True

        return await self._cancel_single_flight.run(item_id, lambda: asyncio.create_task(cancel_task()))

    async def is_recently_canceled(self, item_id: str) -> bool:
        return await self._recently.is_canceled(item_id)


exchange_booking_repository = ExchangeBookingRepository(
    ews_endpoint=settings.exchange.ews_endpoint,
    account_email=settings.exchange.username,
    password=settings.exchange.password.get_secret_value(),
)
