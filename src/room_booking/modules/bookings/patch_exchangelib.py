import datetime as dtm

import exchangelib.folders.base


def get_free_busy_info(self, accounts, start, end, merged_free_busy_interval=30, requested_view="DetailedMerged"):
    """Return free/busy information for a list of accounts.

    :param accounts: A list of (account, attendee_type, exclude_conflicts) tuples, where account is either an
        Account object or a string, attendee_type is a MailboxData.attendee_type choice, and exclude_conflicts is a
        boolean.
    :param start: The start datetime of the request
    :param end: The end datetime of the request
    :param merged_free_busy_interval: The interval, in minutes, of merged free/busy information (Default value = 30)
    :param requested_view: The type of information returned. Possible values are defined in the
        FreeBusyViewOptions.requested_view choices. (Default value = 'DetailedMerged')

    :return: A generator of FreeBusyView objects
    """
    from exchangelib.account import Account
    from exchangelib.properties import (
        DaylightTime,
        FreeBusyViewOptions,
        MailboxData,
        StandardTime,
        TimeWindow,
        TimeZone,
    )
    from exchangelib.services.get_user_availability import GetUserAvailability

    timezone = TimeZone(
        bias=-180,
        standard_time=StandardTime(bias=0, time=dtm.time(0, 0), occurrence=1, iso_month=1, weekday="Monday"),
        daylight_time=DaylightTime(bias=0, time=dtm.time(0, 0), occurrence=5, iso_month=12, weekday="Sunday"),
    )

    return GetUserAvailability(self).call(
        tzinfo=start.tzinfo,
        mailbox_data=[
            MailboxData(
                email=account.primary_smtp_address if isinstance(account, Account) else account,
                attendee_type=attendee_type,
                exclude_conflicts=exclude_conflicts,
            )
            for account, attendee_type, exclude_conflicts in accounts
        ],
        timezone=timezone,
        free_busy_view_options=FreeBusyViewOptions(
            time_window=TimeWindow(start=start, end=end),
            merged_free_busy_interval=merged_free_busy_interval,
            requested_view=requested_view,
        ),
    )


exchangelib.protocol.Protocol.get_free_busy_info = get_free_busy_info

# Optimize request to get calendar items
original_normalize_fields = exchangelib.folders.base.BaseFolder.normalize_fields


def normalize_fields(self, fields):
    additional_fields = original_normalize_fields(self, fields)
    result = []
    for field in additional_fields:
        if field.field.field_uri == "calendar:StartTimeZone" or field.field.field_uri == "calendar:EndTimeZone":
            continue
        result.append(field)
    return result


exchangelib.folders.base.BaseFolder.normalize_fields = normalize_fields
