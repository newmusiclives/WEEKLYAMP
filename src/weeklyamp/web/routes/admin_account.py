"""Admin account self-service routes.

Today: a single change-password screen that lets a logged-in admin
rotate their bcrypt hash without editing Railway env vars. The new
hash is written to `admin_settings.admin_password_hash` (migration v44),
which `_get_admin_hash()` reads in priority order over the env var.

Why this exists: rotating WEEKLYAMP_ADMIN_HASH via the Railway dashboard
is error-prone. The leading `$` in a bcrypt hash gets eaten as a
variable reference and the value is silently mangled. The original
manual rotation flow during the 2026-04-08 incident took several
attempts before it took effect; this route eliminates that whole
class of foot-gun.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from weeklyamp.web.deps import get_repo, render
from weeklyamp.web.security import (
    _get_admin_hash,
    hash_password,
    invalidate_admin_hash_cache,
    is_authenticated,
    verify_password,
)

router = APIRouter()


# Routes are mounted at "/admin" in app.py so the final paths are
# /admin/change-password (GET form) and /admin/change-password (POST).


def _require_admin(request: Request) -> Response | None:
    """Reject unauthenticated callers with a 302 to /login.

    Returns a Response when the caller is unauthenticated, or None
    when the caller is authenticated and the handler should proceed.
    """
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    return None


@router.get("/change-password", response_class=HTMLResponse)
async def change_password_form(request: Request) -> Response:
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect
    return HTMLResponse(render("admin_change_password.html", error="", success=""))


def _render_card(error: str, success: str, *, status_code: int = 200) -> HTMLResponse:
    """Render the form card. The htmx swap target on the form is the
    `.card` element, so we return only that fragment on POST so the
    rest of the page (sidebar, header) is preserved."""
    return HTMLResponse(
        render("admin_change_password_card.html", error=error, success=success),
        status_code=status_code,
    )


@router.post("/change-password")
async def change_password_submit(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
) -> Response:
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    # Validate inputs
    if new_password != confirm_password:
        return _render_card("New password and confirmation do not match.", "", status_code=400)
    if len(new_password) < 12:
        return _render_card("New password must be at least 12 characters.", "", status_code=400)
    if new_password == current_password:
        return _render_card("New password must differ from the current one.", "", status_code=400)

    # Verify the current password against the active hash. We use the
    # same check the login flow uses so behavior matches exactly.
    current_hash = _get_admin_hash()
    if not current_hash or not verify_password(current_password, current_hash):
        return _render_card("Current password is incorrect.", "", status_code=401)

    # Hash the new password and persist it. Cache invalidation is the
    # critical step — without it, the in-process cache keeps serving
    # the old hash until the next worker restart.
    new_hash = hash_password(new_password)
    repo = get_repo()
    repo.set_admin_setting("admin_password_hash", new_hash)
    invalidate_admin_hash_cache()

    return _render_card(
        "",
        "Password updated. Existing sessions remain valid until logout.",
    )
