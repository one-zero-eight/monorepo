"""Bootloader: pytest plugins for Dockerized infra, patched settings/IO, and auth HTTP mocks."""

pytest_plugins = [
    "tests.conftest_better_print_durations",
    "tests.conftest_runtime_settings",
    "tests.conftest_auth",
]
