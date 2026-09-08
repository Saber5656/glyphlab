"""Trust proxy headers only behind a proxy that overwrites them (e.g. Fly).
In-memory limits require one service process; multi-instance needs shared storage.
HSTS is configured by the TLS proxy. Request bodies are bounded before parsing.
"""

import ipaddress
import logging
import re
import time
from uuid import uuid4

from glyphlab.errors import GlyphlabError
from limits import parse
from slowapi import Limiter
from starlette.requests import Request

from .auth import authenticate
from .db.models import AbuseEvent
from .errors import error_response
from .logging import request_id


def client_ip(request):
    peer = request.client.host if request.client else "unknown"
    if not request.app.state.settings.trust_proxy_headers:
        return peer
    value = request.headers.get("fly-client-ip")
    if value is None:
        xff = request.headers.get("x-forwarded-for")
        value = xff.split(",")[-1].strip() if xff else None
    try:
        return str(ipaddress.ip_address(value)) if value else peer
    except ValueError:
        return peer


class SecurityMiddleware:
    def __init__(self, app, state):
        self.app = app
        self.state = state
        self.limiter = Limiter(key_func=lambda: "", storage_uri="memory://").limiter

    def check(self, amount, period, key):
        item = parse(f"{amount}/{period}")
        if not self.limiter.hit(item, key):
            window = self.limiter.get_window_stats(item, key)
            return max(1, int(window.reset_time - time.time()) + 1)
        return None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope, receive)
        rid = request.headers.get("x-request-id", "")
        if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", rid):
            rid = str(uuid4())
        context = request_id.set(rid)
        started = time.monotonic()
        status = 500

        async def secure_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = list(message.get("headers", []))
                present = {k.lower() for k, v in headers}
                content_type = dict(headers).get(b"content-type", b"")
                csp = (
                    (
                        "default-src 'self'; img-src 'self' data: blob:; "
                        "font-src 'self' data: blob:; "
                        "style-src 'self' 'unsafe-inline'; frame-ancestors 'none'"
                    )
                    if b"text/html" in content_type
                    else "default-src 'none'"
                )
                defaults = {
                    "x-content-type-options": "nosniff",
                    "referrer-policy": "no-referrer",
                    "permissions-policy": "camera=(), microphone=(), geolocation=()",
                    "cross-origin-opener-policy": "same-origin",
                    "cross-origin-resource-policy": "same-origin",
                    "content-security-policy": csp,
                    "x-request-id": rid,
                }
                headers.extend(
                    (k.encode(), v.encode())
                    for k, v in defaults.items()
                    if k.encode() not in present
                )
                message = {**message, "headers": headers}
            await send(message)

        try:
            path = scope["path"]
            method = scope["method"]
            ip = client_ip(request)
            settings = self.state.settings
            protected = path.startswith("/api/projects/")
            rates = []
            if path == "/api/projects" and method == "POST":
                rates = [
                    (settings.rl_create_per_minute, "minute", "create-min:" + ip),
                    (settings.rl_create_per_day, "day", "create-day:" + ip),
                ]
            elif protected:
                rates = [(settings.rl_default_per_minute, "minute", "auth:" + ip)]
            for amount, period, key in rates:
                retry = self.check(amount, period, key)
                if retry:
                    with self.state.session_factory.begin() as session:
                        session.add(AbuseEvent(ip=ip, kind="rate_limited"))
                    return await error_response(
                        "E_RATE_LIMITED", headers={"Retry-After": str(retry)}
                    )(scope, receive, secure_send)
            if protected:
                pid = path.split("/")[3]
                project = authenticate(self.state, pid, request.headers.get("authorization"), ip)
                scope.setdefault("state", {})["project"] = project
                if method == "POST" and path.endswith("/uploads"):
                    rates = [
                        (settings.rl_uploads_per_hour_ip, "hour", "uploads:" + ip),
                        (settings.rl_uploads_per_hour_project, "hour", "proj-upload:" + project.id),
                    ]
                elif method == "POST" and path.endswith("/builds"):
                    rates = [
                        (settings.rl_builds_per_hour_project, "hour", "proj-build:" + project.id)
                    ]
                else:
                    rates = []
                for amount, period, key in rates:
                    retry = self.check(amount, period, key)
                    if retry:
                        with self.state.session_factory.begin() as session:
                            session.add(AbuseEvent(ip=ip, kind="rate_limited"))
                        return await error_response(
                            "E_RATE_LIMITED", headers={"Retry-After": str(retry)}
                        )(scope, receive, secure_send)
            if method in {"POST", "PUT", "PATCH"}:
                header = request.headers.get("content-length")
                if header is None:
                    return await error_response("E_VALIDATION", status=411)(
                        scope, receive, secure_send
                    )
                try:
                    length = int(header)
                except ValueError:
                    length = -1
                if length < 0:
                    return await error_response("E_VALIDATION")(scope, receive, secure_send)
                cap = (
                    settings.max_upload_request_bytes
                    if path.endswith("/uploads")
                    else settings.max_json_body_bytes
                )
                if length > cap:
                    return await error_response("E_REQUEST_TOO_LARGE")(scope, receive, secure_send)
                size = 0
                chunks = []
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    size += len(chunk)
                    if size > cap:
                        return await error_response("E_REQUEST_TOO_LARGE")(
                            scope, receive, secure_send
                        )
                    chunks.append(chunk)
                    if not message.get("more_body"):
                        break
                sent = False

                async def bounded_receive():
                    nonlocal sent
                    if not sent:
                        sent = True
                        return {
                            "type": "http.request",
                            "body": b"".join(chunks),
                            "more_body": False,
                        }
                    return await receive()

                await self.app(scope, bounded_receive, secure_send)
            else:
                await self.app(scope, receive, secure_send)
        except GlyphlabError as exc:
            await error_response(exc.code, detail=exc.detail)(scope, receive, secure_send)
        except Exception:
            logging.getLogger("glyphlab_service").error(
                "Unhandled request error", extra={"error_code": "E_INTERNAL"}
            )
            await error_response("E_INTERNAL")(scope, receive, secure_send)
        finally:
            route = scope.get("route")
            template = getattr(route, "path", "unmatched")
            logging.getLogger("glyphlab_service").info(
                "%s %s %s %.1fms",
                scope["method"],
                template,
                status,
                (time.monotonic() - started) * 1000,
            )
            request_id.reset(context)
