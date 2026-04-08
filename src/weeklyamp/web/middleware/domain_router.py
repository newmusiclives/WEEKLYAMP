"""White-label domain routing middleware.

Maps custom domains to specific newsletter editions for white-label SaaS support.
INACTIVE by default — requires white_label.enabled=true.
"""

from __future__ import annotations

import logging
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class DomainRoutingMiddleware(BaseHTTPMiddleware):
    """Route requests to edition-specific content based on Host header.

    When a custom domain is configured for an edition (e.g., nashville.truefansnewsletters.com
    or nashvillemusic.com), this middleware sets the edition context on the request state
    so that templates render with the edition's branding.
    """

    def __init__(self, app, config=None):
        super().__init__(app)
        self.config = config
        self._domain_cache: dict[str, dict] = {}
        self._cache_built = False

    def _build_cache(self) -> None:
        """Build domain → tenant mapping from database.

        Two tenant types are supported:
            type='licensee'  — per-licensee custom domain (preferred)
            type='edition'   — per-edition custom domain (legacy)
        """
        if self._cache_built or not self.config:
            return
        if not self.config.white_label.enabled:
            self._cache_built = True
            return
        try:
            from weeklyamp.web.deps import get_repo
            repo = get_repo()
            conn = repo._conn()

            # Licensee custom domains (verified only)
            try:
                rows = conn.execute(
                    "SELECT id, company_name, custom_domain, logo_url, "
                    "primary_color, footer_html, sender_name, reply_to_email, "
                    "city_market_slug, edition_slugs "
                    "FROM licensees "
                    "WHERE custom_domain != '' AND domain_verified = 1 "
                    "AND status IN ('active','trialing')"
                ).fetchall()
                for row in rows:
                    d = dict(row)
                    domain = (d.get("custom_domain") or "").lower().strip()
                    if domain:
                        d["_tenant_type"] = "licensee"
                        self._domain_cache[domain] = d
            except Exception:
                logger.debug("licensee domain lookup skipped", exc_info=True)

            # Legacy: per-edition custom domains
            try:
                rows = conn.execute(
                    "SELECT slug, custom_domain, custom_logo_url, custom_css, custom_footer_html "
                    "FROM newsletter_editions WHERE custom_domain != ''"
                ).fetchall()
                for row in rows:
                    d = dict(row)
                    domain = (d.get("custom_domain") or "").lower().strip()
                    if domain and domain not in self._domain_cache:
                        d["_tenant_type"] = "edition"
                        self._domain_cache[domain] = d
            except Exception:
                logger.debug("edition domain lookup skipped", exc_info=True)

            conn.close()
            self._cache_built = True
            logger.info(
                "Domain routing cache built: %d custom domains",
                len(self._domain_cache),
            )
        except Exception:
            logger.exception("Failed to build domain routing cache")

    def invalidate_cache(self) -> None:
        """Force cache rebuild on next request. Call when a licensee
        domain is verified or a custom_domain field is changed."""
        self._domain_cache = {}
        self._cache_built = False

    def _lookup(self, host: str) -> Optional[dict]:
        self._build_cache()
        host = host.lower().split(":")[0]
        return self._domain_cache.get(host)

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.config or not self.config.white_label.enabled:
            return await call_next(request)

        host = request.headers.get("host", "")
        tenant = self._lookup(host)
        if tenant:
            ttype = tenant.get("_tenant_type")
            if ttype == "licensee":
                request.state.licensee_id = tenant.get("id")
                request.state.licensee = tenant
                request.state.brand_logo_url = tenant.get("logo_url", "")
                request.state.brand_primary_color = tenant.get("primary_color", "")
                request.state.brand_footer_html = tenant.get("footer_html", "")
                request.state.white_label_edition = None
            else:
                request.state.licensee_id = None
                request.state.white_label_edition = tenant
                request.state.brand_logo_url = tenant.get("custom_logo_url", "")
                request.state.brand_primary_color = ""
                request.state.brand_footer_html = tenant.get("custom_footer_html", "")
        else:
            request.state.licensee_id = None
            request.state.licensee = None
            request.state.white_label_edition = None

        return await call_next(request)
