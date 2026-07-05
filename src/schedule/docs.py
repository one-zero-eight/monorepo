import re

from fastapi.routing import APIRoute

from src.common_fastapi import MIT_LICENSE_INFO, ONE_ZERO_EIGHT_CONTACT_INFO

TITLE = "InNoHassle Schedule API"
SUMMARY = "Browse and create schedules at Innopolis University."
DESCRIPTION = """
### About this project

This is the API for the Schedule service in the InNoHassle ecosystem developed by the one-zero-eight community.

Using this API you can browse, view, create and edit schedules at Innopolis University.

Useful links:
- [InNoHassle Schedule](https://innohassle.ru/schedule)
"""
CONTACT_INFO = ONE_ZERO_EIGHT_CONTACT_INFO
LICENSE_INFO = MIT_LICENSE_INFO

TAGS_INFO = [
    {
        "name": "Event Groups",
        "description": (
            "Groups consisting of multiple events. It can represent a schedule of one academic group or club."
        ),
    },
    {
        "name": "ICS",
        "description": "Generate .ics to import them into calendar app.",
    },
    {
        "name": "Tags",
        "description": "Topics or categories of event groups.",
    },
    {
        "name": "Users",
        "description": "User data and linking users with event groups.",
    },
]


def generate_unique_operation_id(route: APIRoute) -> str:
    if route.tags:
        operation_id = f"{route.tags[0]}_{route.name}".lower()
    else:
        operation_id = route.name.lower()
    return re.sub(r"\W+", "_", operation_id)
