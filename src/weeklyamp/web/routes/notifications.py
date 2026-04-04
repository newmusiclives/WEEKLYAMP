"""Notification center routes."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from weeklyamp.web.deps import get_config, get_repo, render

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def notifications_page(request: Request):
    repo = get_repo()
    notifications = repo.get_notifications(limit=50)
    unread_count = repo.get_unread_count()
    return HTMLResponse(render("notifications.html", notifications=notifications, unread_count=unread_count))


@router.post("/{notification_id}/read", response_class=HTMLResponse)
async def mark_read(notification_id: int, request: Request):
    repo = get_repo()
    repo.mark_notification_read(notification_id)
    return HTMLResponse('<span class="badge badge-muted">read</span>')


@router.post("/read-all", response_class=HTMLResponse)
async def mark_all_read(request: Request):
    repo = get_repo()
    repo.mark_all_notifications_read()
    return HTMLResponse('<div class="alert alert-success">All notifications marked as read.</div>')
