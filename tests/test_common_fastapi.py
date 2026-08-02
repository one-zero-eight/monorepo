import logging
from types import SimpleNamespace

from fastapi import FastAPI

from src.common_fastapi import tune_fastapi


def test_tune_fastapi_skips_metrics_without_settings(monkeypatch):
    import src.config_root_schema

    monkeypatch.setattr(
        src.config_root_schema,
        "load_root_settings",
        lambda: SimpleNamespace(metrics=None),
    )
    app = FastAPI()

    tune_fastapi(
        app,
        logger=logging.getLogger(__name__),
        metrics_namespace="test",
        use_auto_derive_route=False,
        use_fastapi_swagger_patch=False,
        use_custom_exception_handlers=False,
    )

    assert all(getattr(route, "path", None) != "/metrics" for route in app.routes)
