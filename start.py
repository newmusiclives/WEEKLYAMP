"""Railway entrypoint — reads PORT and starts uvicorn."""
import os

port = int(os.environ.get("PORT", 8000))
workers = int(os.environ.get("WEB_CONCURRENCY", 1))

import uvicorn
uvicorn.run(
    "weeklyamp.web.app:create_app",
    host="0.0.0.0",
    port=port,
    workers=workers,
    factory=True,
    log_level=os.environ.get("LOG_LEVEL", "info"),
    proxy_headers=True,
    forwarded_allow_ips="*",
)
