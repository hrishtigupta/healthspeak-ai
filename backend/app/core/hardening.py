"""Security hardening applied to every request (Phase 9).

- Security headers; API responses are never cached (they contain patient data).
- Requests that announce a body bigger than the limit are refused before the
  body is read (audio uploads are the only large requests).
- Uvicorn access logs are written WITHOUT query strings, because search terms
  such as ?q=<patient name> must not end up in log files.
- In production, refuse to start with placeholder secrets.
"""

import json
import logging

from app.core.config import Settings

SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", b"camera=(), geolocation=(), microphone=()"),
    (b"cross-origin-resource-policy", b"same-site"),
]
NO_STORE = (b"cache-control", b"no-store")


class SecurityMiddleware:
    """Pure ASGI middleware (does not buffer bodies, works with uploads)."""

    def __init__(self, app, max_body_bytes: int):
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        length = dict(scope.get("headers") or []).get(b"content-length")
        if length is not None and length.isdigit() and int(length) > self.max_body_bytes:
            body = json.dumps({"detail": "Request is too large."}).encode()
            await send({"type": "http.response.start", "status": 413,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"content-length", str(len(body)).encode()), *SECURITY_HEADERS]})
            await send({"type": "http.response.body", "body": body})
            return
        is_api = scope.get("path", "").startswith("/api/")

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.extend(SECURITY_HEADERS)
                if is_api:
                    headers.append(NO_STORE)
                message["headers"] = headers
            await send(message)

        return await self.app(scope, receive, send_with_headers)


class StripQueryFromAccessLog(logging.Filter):
    """uvicorn.access records carry (client, method, full_path, http_version, status)."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) == 5 and isinstance(args[2], str) and "?" in args[2]:
            record.args = (args[0], args[1], args[2].split("?", 1)[0] + "?[removed]", args[3], args[4])
        return True


def install_log_filter() -> None:
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, StripQueryFromAccessLog) for f in logger.filters):
        logger.addFilter(StripQueryFromAccessLog())


class UnsafeProductionConfig(RuntimeError):
    pass


def check_production(settings: Settings) -> None:
    """Fail fast if a production deployment still uses development placeholders."""
    if settings.app_env != "production":
        return
    problems = []
    if "change-me" in settings.database_url:
        problems.append("DATABASE_URL still contains the example password")
    if settings.seed_demo_password:
        problems.append("SEED_DEMO_PASSWORD is set (demo accounts must not exist in production)")
    if any("localhost" in o or "127.0.0.1" in o for o in settings.cors_origin_list):
        problems.append("CORS_ORIGINS still allows localhost")
    if settings.audio_keep_after_processing:
        problems.append("AUDIO_KEEP_AFTER_PROCESSING is on: confirm a documented retention policy first")
    if problems:
        raise UnsafeProductionConfig("Refusing to start in production: " + "; ".join(problems))
