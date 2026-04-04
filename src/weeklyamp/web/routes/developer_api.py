"""Developer API management — API keys and documentation."""
from __future__ import annotations
import secrets
import hashlib
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from weeklyamp.web.deps import get_config, get_repo, render

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def api_management(request: Request):
    repo = get_repo()
    conn = repo._conn()
    keys = conn.execute("SELECT id, name, key_prefix, permissions, rate_limit, is_active, last_used_at, created_at FROM api_keys ORDER BY created_at DESC").fetchall()
    conn.close()
    return HTMLResponse(render("developer_api.html", keys=[dict(k) for k in keys]))

@router.post("/keys/create", response_class=HTMLResponse)
async def create_api_key(request: Request, name: str = Form(...), permissions: str = Form("read")):
    repo = get_repo()
    raw_key = f"tf_{secrets.token_hex(24)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    prefix = raw_key[:10]
    conn = repo._conn()
    conn.execute(
        "INSERT INTO api_keys (name, key_hash, key_prefix, permissions) VALUES (?, ?, ?, ?)",
        (name, key_hash, prefix, permissions),
    )
    conn.commit()
    conn.close()
    return HTMLResponse(f'<div class="alert alert-success"><strong>API Key Created:</strong> <code>{raw_key}</code><br><small>Save this key — it won\'t be shown again.</small></div>')
