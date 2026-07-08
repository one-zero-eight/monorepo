__all__ = ["app"]

import asyncio
import pprint
import time as tm
from contextlib import asynccontextmanager

import exchangelib.errors
from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from src.common_config import Environment
from src.common_fastapi import (
    MIT_LICENSE_INFO,
    ONE_ZERO_EIGHT_CONTACT_INFO,
    generate_unique_operation_id,
    popule_openapi_tags,
    tune_fastapi,
)
from src.inh_accounts_sdk import inh_accounts
from src.logging_ import logger

from .config import settings

DESCRIPTION = """
### About this project

This is the API for Room booking project in InNoHassle ecosystem developed by one-zero-eight community.

Using this API you can view the booking status of rooms at Innopolis University.

Note: API is unstable. Endpoints and models may change in the future.

Useful links:
- [Room booking API source code](https://github.com/one-zero-eight/monorepo/tree/main/src/room_booking)
- [InNoHassle Website](https://innohassle.ru/)
"""


async def _log_bmp_calendar() -> None:
    from src.room_booking.modules.bmp.repository import bmp_repository

    try:
        calendar = await asyncio.to_thread(lambda: bmp_repository.selected_calendar)
    except Exception:  # noqa: BLE001
        logger.exception(f"Failed to resolve BMP calendar for {bmp_repository.account_email}")
        return
    logger.info(
        f"BMP calendar: name={calendar.name} id={calendar.id} path={calendar.absolute} "
        f"account={bmp_repository.account_email}"
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from src.room_booking.modules.bmp.repository import bmp_repository
    from src.room_booking.modules.bookings.exchange_repository import exchange_booking_repository

    await inh_accounts.update_key_set()

    exchange_subscription_task: asyncio.Task[None] | None = None
    if settings.environment != Environment.TESTING:
        await _log_bmp_calendar()

        await bmp_repository.start_inbox_poller()
        await exchange_booking_repository.start_inbox_poller()

        async def print_exchanglelib_status_and_start_subscription():
            status = await exchange_booking_repository.get_server_status()
            if status:
                logger.info(f"Exchange server status: {status}")
            else:
                logger.error("Failed to get exchange server status")

            if settings.exchange.ews_callback_url is not None:
                logger.info(f"Starting exchange subscription to {settings.exchange.ews_callback_url}")

                while True:
                    now = tm.monotonic()
                    if (
                        exchange_booking_repository.last_callback_time is None
                        or (now - exchange_booking_repository.last_callback_time) > 60 * 2
                    ):
                        subscription = await exchange_booking_repository.push_subscription(
                            callback_url=settings.exchange.ews_callback_url
                        )
                        logger.info(f"Exchange subscription started: {subscription=}")
                    await asyncio.sleep(60)

        exchange_subscription_task = asyncio.create_task(print_exchanglelib_status_and_start_subscription())

    yield

    if settings.environment != Environment.TESTING:
        if exchange_subscription_task is not None:
            exchange_subscription_task.cancel()
            try:
                await exchange_subscription_task
            except asyncio.CancelledError:
                pass
        await bmp_repository.stop_inbox_poller()
        await exchange_booking_repository.stop_inbox_poller()


app = FastAPI(
    title="InNoHassle Room booking API",
    summary="View the booking status of rooms at Innopolis University.",
    description=DESCRIPTION,
    version="0.1.0",
    contact=ONE_ZERO_EIGHT_CONTACT_INFO,
    license_info=MIT_LICENSE_INFO,
    openapi_tags=[],
    servers=[
        {"url": settings.app_root_path, "description": "Current"},
        {
            "url": "https://api.innohassle.ru/room-booking/v0",
            "description": "Production environment",
        },
        {
            "url": "https://api.innohassle.ru/room-booking/staging-v0",
            "description": "Staging environment",
        },
    ],
    root_path=settings.app_root_path,
    root_path_in_servers=False,
    generate_unique_id_function=generate_unique_operation_id,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    swagger_ui_oauth2_redirect_url=None,
)
tune_fastapi(app, logger=logger)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import src.room_booking.modules.bmp.routes  # noqa: E402
import src.room_booking.modules.bookings.routes  # noqa: E402
import src.room_booking.modules.rooms.routes  # noqa: E402

app.include_router(src.room_booking.modules.rooms.routes.router)
popule_openapi_tags(app, src.room_booking.modules.rooms.routes)
app.include_router(src.room_booking.modules.bookings.routes.router)
popule_openapi_tags(app, src.room_booking.modules.bookings.routes)
app.include_router(src.room_booking.modules.bmp.routes.router)
popule_openapi_tags(app, src.room_booking.modules.bmp.routes)


@app.exception_handler(exchangelib.errors.EWSError)
async def ews_error_handler(
    request: Request,
    exc: exchangelib.errors.EWSError,
):
    logger.warning(f"EWS error, probably Outlook is down: {exc}", exc_info=True)
    return JSONResponse(status_code=429, content={"detail": f"EWS error, probably Outlook is down: {exc}"})


@app.post("/ews-callback", include_in_schema=False)
async def ews_callback(request: Request):
    """
    EWS callback endpoint for push subscription.
    https://ecederstrand.github.io/exchangelib/#synchronization-subscriptions-and-notifications
    """
    from collections.abc import Iterable
    from typing import cast

    from exchangelib.properties import (
        ItemId,
        ModifiedEvent,
        Notification,
        TimestampEvent,
    )
    from exchangelib.services import SendNotification

    from src.room_booking.modules.bookings.exchange_repository import exchange_booking_repository
    from src.room_booking.modules.bookings.service import get_emails_to_attendees_index

    ws = SendNotification(protocol=None)
    data = ws.ok_payload()
    for notification in ws.parse(await request.body()):
        logger.info("Notification from Exchange")
        if not isinstance(notification, Notification):
            logger.warning("Notification from Exchange is not a Notification object")
            continue

        if notification.subscription_id != exchange_booking_repository.subscription_id:
            logger.warning("Notification from Exchange with wrong subscription ID, unsubscribing")
            data = ws.unsubscribe_payload()
            break

        exchange_booking_repository.last_callback_time = tm.monotonic()

        for event in cast(Iterable[TimestampEvent], notification.events):
            logger.info(f"Event: {type(event)}\n{pprint.pformat(event, sort_dicts=False, compact=True)}")

            if isinstance(event, ModifiedEvent) and event.item_id is not None:
                item_id = str(cast(ItemId, event.item_id).id)
                if await exchange_booking_repository.is_recently_canceled(item_id):
                    logger.info(f"Booking {item_id} was recently canceled, so we skipping")
                    continue
                booking = await exchange_booking_repository.get_booking(item_id)
                if booking is None:
                    logger.warning("Booking not found")
                    continue
                email_index = get_emails_to_attendees_index(booking)

                for email, attendee in email_index.items():
                    if attendee.response_type == "Decline":
                        logger.warning(f"Attendee ({email}) declined the booking, so we will delete this booking")
                        await exchange_booking_repository.cancel_booking(booking, email)
                        logger.info(f"Booking deleted: {item_id}")
                        break

    return Response(content=data, status_code=201, media_type="text/xml; charset=utf-8")


# FIXME: came up with internal mechanism for checking status instead of uptime.dofi4ka.ru
class UptimeSchema(BaseModel):
    class Status(BaseModel):
        status: int
        time: str
        ping: int | None

    uptime: list[Status]


@app.get("/status")
async def get_status() -> UptimeSchema:
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.get("https://uptime.dofi4ka.ru/api/status-page/heartbeat/innopolis")

    payload = response.json()
    uptime = payload["heartbeatList"]["20"]

    return UptimeSchema.model_validate({"uptime": uptime})
