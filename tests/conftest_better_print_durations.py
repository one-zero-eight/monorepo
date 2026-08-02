def pytest_configure(config):
    try:
        import pytest_durations.helpers as helpers
        import pytest_durations.reporting as reporting
    except ImportError:
        return

    def get_fixture_key(fixturedef, item):
        if fixturedef.baseid:
            baseid = fixturedef.baseid
        elif fixturedef.node is not None:
            baseid = helpers.get_test_key(item=item)
        else:
            baseid = ""
        return "::".join(filter(None, (baseid, fixturedef.argname)))

    helpers.get_fixture_key = get_fixture_key  # ty: ignore[invalid-assignment]

    def format_seconds(seconds: float) -> str:
        return f"{seconds:.3f}s"

    @classmethod
    def from_time_value(cls, time_value):
        return cls(
            total=format_seconds(time_value.sum),
            name=time_value.name,
            num=str(time_value.calls),
            med=format_seconds(time_value.med),
            min=format_seconds(time_value.min),
            max=format_seconds(time_value.max),
        )

    reporting.ReportRowT.from_time_value = from_time_value  # ty: ignore[invalid-assignment]
