"""Optional personal-phone access through a loopback Tailscale Serve proxy.

Only enable with the provided launcher (--no-proxy-headers). Identity headers
are trusted solely from the local Serve process, never from a network socket.
"""

import logging
import secrets
from time import monotonic
from urllib.parse import urlsplit

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

from .security_headers import SECURITY_HEADERS

LOOPBACK = ("localhost", "127.0.0.1", "::1")


def hostname(url):
    try:
        return urlsplit(url).hostname
    except ValueError:
        return None


def desktop_request(request):
    return bool(request.client and request.client.host in LOOPBACK
                and request.url.hostname in LOOPBACK
                and not any(name in request.headers for name in
                            ("forwarded", "x-forwarded-for", "x-forwarded-host", "tailscale-user-login")))


def private_settings(origin="", user=""):
    if not origin and not user:
        return "", ""
    parsed = urlsplit(origin)
    if (not user.strip() or parsed.scheme != "https" or not parsed.hostname
            or not parsed.hostname.endswith(".ts.net") or parsed.username or parsed.password
            or parsed.port not in (None, 443) or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment):
        raise ValueError("Set DAYMARK_PRIVATE_ORIGIN to your HTTPS .ts.net origin and DAYMARK_PRIVATE_USER to your Tailscale login.")
    return f"https://{parsed.netloc.lower()}", user.strip()


class PrivateAccessMiddleware:
    def __init__(self, app, origin="", user=""):
        self.app = app
        self.origin, self.user = private_settings(origin, user)

    def allowed(self, scope):
        headers = Headers(scope=scope)
        peer = (scope.get("client") or ("",))[0]
        host = headers.get("host", "").lower()
        local_host = hostname("http://" + host) in LOOPBACK
        forwarded = any(name in headers for name in ("forwarded", "x-forwarded-for", "x-forwarded-host", "tailscale-user-login"))
        local = peer in LOOPBACK and local_host and not forwarded
        private = bool(self.origin and peer in LOOPBACK and host == urlsplit(self.origin).netloc
                       and secrets.compare_digest(headers.get("tailscale-user-login", "").encode(), self.user.encode()))
        allowed_origin = not headers.get("origin") or (
            headers["origin"] == self.origin if private else hostname(headers["origin"]) in LOOPBACK)
        return (local or private) and allowed_origin

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = secrets.token_hex(12)
        started = monotonic()
        response_status = 500
        response_started = False

        async def respond(message):
            nonlocal response_status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                response_status = message["status"]
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Request-ID"] = request_id
                for name, value in SECURITY_HEADERS.items():
                    response_headers.setdefault(name, value)
                if scope["path"].startswith("/api/"):
                    response_headers["Cache-Control"] = "no-store"
            await send(message)

        try:
            if self.allowed(scope):
                await self.app(scope, receive, respond)
            else:
                await JSONResponse({"detail": "Open Daymark locally, or start private phone access with --phone."}, status_code=403,
                                   headers={"Cache-Control": "no-store"})(scope, receive, respond)
        except Exception:
            logging.getLogger("daymark.requests").exception("Unexpected request failure", extra={"request_id": request_id})
            if response_started:
                raise
            await JSONResponse({"detail": "The server encountered an internal error. Use the request ID when reporting it."},
                               status_code=500, headers={"Cache-Control": "no-store"})(scope, receive, respond)
        finally:
            route = scope.get("route")
            logging.getLogger("daymark.requests").info("Request completed", extra={
                "request_id": request_id, "method": scope["method"],
                "route": getattr(route, "path", "unmatched"), "status": response_status,
                "duration_ms": round((monotonic() - started) * 1000, 2)})
