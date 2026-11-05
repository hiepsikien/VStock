"""The Studio UI and the backend share one endpoint list.

`src/studio/api.ts` builds every Studio URL from a single prefix, so a frontend
change can start calling a route before the backend serves it. That is exactly
how the rollback button shipped against a missing route. This test pins the
paths the UI calls; when the UI grows a call, add it here in the same change.
"""

from __future__ import annotations

from app.main import app

# Mirrors the calls in `src/studio/api.ts` (plus the spec/rollback helpers).
UI_ROUTES = {
    ("POST", "/v1/studio/sentence/validate"),
    ("POST", "/v1/studio/sentence/preview"),
    ("POST", "/v1/studio/jobs"),
    ("GET", "/v1/studio/jobs/{job_id}"),
    ("POST", "/v1/studio/sentence/audio"),
    ("POST", "/v1/studio/sentence/publish"),
    ("GET", "/v1/studio/sentence/examples"),
    ("GET", "/v1/studio/sentence/specs"),
    ("GET", "/v1/studio/sentence/specs/{spec_id}"),
    ("POST", "/v1/studio/sentence/specs/{spec_id}/rollback"),
    # Phase 1 vision/session calls made by the Studio UI.
    ("GET", "/v1/musicalize/studio/access"),
    ("POST", "/v1/musicalize/studio/uploads"),
    ("GET", "/v1/musicalize/studio/uploads/{upload_id}"),
    ("DELETE", "/v1/musicalize/studio/uploads/{upload_id}"),
    ("POST", "/v1/musicalize/studio/analyze"),
}


def _served_routes() -> set[tuple[str, str]]:
    served: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        for method in getattr(route, "methods", ()) or ():
            served.add((method, path))
    return served


def test_every_studio_route_the_ui_calls_is_served() -> None:
    served = _served_routes()
    missing = sorted(UI_ROUTES - served)
    assert not missing, f"UI calls routes the backend does not serve: {missing}"


def test_rollback_route_is_served_by_the_publish_router() -> None:
    assert ("POST", "/v1/studio/sentence/specs/{spec_id}/rollback") in _served_routes()
