"""Admin feature flag toggle UI.

Mounted at /admin/feature-flags (see app.py). Grouped by category, with
htmx-powered per-toggle POST that writes the DB and invalidates the
in-process cache immediately. No page reload needed.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from weeklyamp.core.feature_flags import (
    FLAG_METADATA,
    enabled,
    invalidate_cache,
)
from weeklyamp.web.deps import get_repo, render
from weeklyamp.web.security import is_authenticated

router = APIRouter()


def _require_admin(request: Request) -> Response | None:
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    return None


def _grouped_flags() -> dict[str, list[dict]]:
    """Return flags grouped by category, preserving FLAG_METADATA order.

    Each flag dict has: key, label, description, enabled (current value).
    """
    groups: dict[str, list[dict]] = {}
    for key, (label, category, description) in FLAG_METADATA.items():
        cat = category or "Other"
        groups.setdefault(cat, []).append({
            "key": key,
            "label": label,
            "description": description,
            "enabled": enabled(key),
        })
    return groups


@router.get("/feature-flags", response_class=HTMLResponse)
async def feature_flags_page(request: Request) -> Response:
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect
    return HTMLResponse(render("admin_feature_flags.html", groups=_grouped_flags()))


@router.post("/feature-flags/toggle")
async def feature_flags_toggle(
    request: Request,
    key: str = Form(...),
    enabled_value: str = Form(""),
) -> Response:
    """htmx POST target. Form posts key=<flag>&enabled_value=on|<empty>.

    An unchecked checkbox does not submit its value, so an empty
    `enabled_value` means "turn off" and "on" means "turn on".
    """
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect
    if key not in FLAG_METADATA:
        # Reject unknown flag keys — prevents writing arbitrary rows
        # via a crafted POST.
        return HTMLResponse("Unknown flag", status_code=400)

    new_value = enabled_value.lower() in ("on", "true", "1", "yes")
    label, category, description = FLAG_METADATA[key]
    repo = get_repo()
    repo.set_feature_flag(key, new_value, description=description, category=category)
    invalidate_cache(key)

    # Return a fragment the htmx swap can drop back into the row so the
    # toggle visibly reflects the new state without a page reload.
    return HTMLResponse(
        render(
            "admin_feature_flags_row.html",
            flag={
                "key": key,
                "label": label,
                "description": description,
                "enabled": new_value,
            },
        )
    )
