import asyncio
import secrets
import threading
import time
from collections import deque
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import ROOT, Settings
from .demo import demo_records
from .models import Input, Preferences, Record
from .providers import ProviderError, Providers
from .store import Store, digest
from .transfer import parse_csv, parse_ics, write_csv

Provider = Literal["google", "microsoft", "bennett"]
CampusSource = Literal["bennett-lms", "camu", "csv", "ics", "demo"]
COOKIE = "daymark_session"
DIST = ROOT / "frontend" / "dist"
MAX_UPLOAD = 2_000_000


class Login(Input):
    password: str = Field(min_length=1, max_length=1024)


class StudyPlan(Input):
    revision: str = Field(min_length=64, max_length=64)
    blocks: list[Record] = Field(min_length=1, max_length=150)


class Duplicate(Input):
    revision: str = Field(min_length=64, max_length=64)
    mate: str = Field(min_length=1, max_length=64)
    expected: str = Field(min_length=1, max_length=4096)


def create_app(config=None, transport=None):
    cfg = config or Settings()
    store = Store(cfg.db)
    providers = Providers(cfg, store, transport)
    from urllib.parse import urlsplit
    hostname = urlsplit(cfg.origin).hostname
    attempts = deque()
    auth_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(_app):
        store.init()
        if providers.available("bennett") and not store.connection("bennett"):
            store.connect("bennett", digest(cfg.bennett_url))

        async def periodic():
            while True:
                for provider in providers.locks:
                    await asyncio.to_thread(providers.sync, provider)
                await asyncio.sleep(cfg.sync_seconds)

        task = asyncio.create_task(periodic()) if cfg.sync_seconds else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="Daymark", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[hostname])

    @app.middleware("http")
    async def headers(request, call_next):
        if request.url.path.startswith("/api/") and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if request.headers.get("origin") != cfg.origin:
                return JSONResponse({"detail": "Request origin does not match DAYMARK_ORIGIN"}, status_code=403)
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if request.headers.get("host") == urlsplit(cfg.origin).netloc and DIST.is_dir():
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
            )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation(_request, error):
        issue = error.errors()[0]
        fields = ".".join(str(part) for part in issue["loc"][1:])
        return JSONResponse({"detail": f"{fields + ': ' if fields else ''}{issue['msg']}"}, status_code=422)

    def issue(response):
        token = secrets.token_urlsafe(32)
        store.issue_session(token)
        response.set_cookie(COOKIE, token, max_age=604800, httponly=True, secure=cfg.secure, samesite="lax")
        return token

    def require(request: Request, response: Response):
        token = request.cookies.get(COOKIE, "")
        if token and store.valid_session(token):
            return token
        if not cfg.password:
            return issue(response)
        raise HTTPException(401, "Sign in to Daymark")

    secure = [Depends(require)]

    @app.post("/api/login")
    def login(body: Login, response: Response):
        with auth_lock:
            now = time.monotonic()
            while attempts and now - attempts[0] > 60:
                attempts.popleft()
            if len(attempts) >= 8:
                raise HTTPException(429, "Too many attempts. Try again in a minute.")
            if cfg.password and not secrets.compare_digest(digest(body.password), digest(cfg.password)):
                attempts.append(now)
                raise HTTPException(401, "Incorrect password")
            attempts.clear()
        issue(response)
        return {"ok": True}

    @app.post("/api/logout", dependencies=secure)
    def logout(request: Request, response: Response):
        store.revoke_session(request.cookies.get(COOKIE, ""))
        response.delete_cookie(COOKIE)
        return {"ok": True}

    def status():
        states = store.connection_status()
        return {name: {"available": providers.available(name), "connected": name in states,
                       "synced": states.get(name, {}).get("synced"), "error": states.get(name, {}).get("error")}
                for name in providers.locks}

    @app.get("/api/workspace", dependencies=secure)
    def workspace():
        return {**store.snapshot(), "connections": status(), "protected": bool(cfg.password)}

    @app.post("/api/records", status_code=201, dependencies=secure)
    def create(body: Record):
        return store.save(body)

    @app.put("/api/records/{record_id}", dependencies=secure)
    def update(record_id: str, body: Record):
        if record := store.save(body, record_id):
            return record
        raise HTTPException(404, "Editable record not found")

    @app.delete("/api/records/{record_id}", dependencies=secure)
    def delete(record_id: str):
        if not store.delete(record_id):
            raise HTTPException(404, "Editable record not found")
        return {"ok": True}

    @app.put("/api/preferences", dependencies=secure)
    def preferences(body: Preferences):
        return store.preferences(body)

    @app.post("/api/plan", dependencies=secure)
    def plan(body: StudyPlan):
        for block in body.blocks:
            if block.kind != "event" or block.category != "study" or block.repeat != "none":
                raise HTTPException(422, "A plan can only add one-time study blocks")
            if len(block.start) == 10 or datetime.fromisoformat(block.start) < datetime.now(timezone.utc):
                raise HTTPException(409, "A proposed block has already started. Generate a fresh preview.")
        if not store.add_plan(body.revision, body.blocks):
            raise HTTPException(409, "Your workspace changed. Generate a fresh preview.")
        return {"count": len(body.blocks)}

    @app.put("/api/duplicates/{record_id}", dependencies=secure)
    def dismiss(record_id: str, body: Duplicate):
        if not store.dismiss(body.revision, record_id, body.mate, body.expected):
            raise HTTPException(409, "The suggested match changed. Refresh and review it again.")
        return {"ok": True}

    @app.delete("/api/duplicates/{record_id}", dependencies=secure)
    def restore(record_id: str):
        store.restore(record_id)
        return {"ok": True}

    @app.post("/api/import/{source}", dependencies=secure)
    async def import_file(source: CampusSource, request: Request, format: Literal["csv", "ics"]):
        if source == "demo":
            raise HTTPException(400, "Use the sample data action")
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_UPLOAD:
                raise HTTPException(413, "Choose a file smaller than 2 MB")
        zone = ZoneInfo((await asyncio.to_thread(store.snapshot))["preferences"]["timezone"])
        try:
            entries = await asyncio.to_thread(parse_csv if format == "csv" else parse_ics, bytes(data), zone,
                                               *((source,) if format == "ics" else ()))
        except (ValueError, TypeError, KeyError, OverflowError, UnicodeError) as error:
            details = str(error) if format == "csv" and str(error).startswith("CSV") else "Check the file format and required fields."
            raise HTTPException(422, details) from None
        await asyncio.to_thread(store.import_records, source, entries)
        return {"count": len(entries)}

    @app.delete("/api/import/{source}", dependencies=secure)
    def clear_import(source: CampusSource):
        store.clear_import(source)
        return {"ok": True}

    @app.post("/api/demo", dependencies=secure)
    def demo():
        entries = demo_records(store.snapshot()["preferences"]["timezone"])
        store.import_records("demo", entries)
        return {"count": len(entries)}

    @app.get("/api/export.csv", dependencies=secure)
    def export():
        return Response(write_csv(store.snapshot()["records"]), media_type="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="daymark.csv"'})

    @app.post("/api/connections/{provider}/start")
    def connect(provider: Provider, session: str = Depends(require)):
        if not providers.available(provider):
            raise HTTPException(503, "Configure this provider in your .env file first")
        if provider == "bennett":
            store.connect(provider, digest(cfg.bennett_url))
            return {"url": None}
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
        store.oauth_state(state, provider, session, verifier)
        return {"url": providers.authorization(provider, state, verifier)}

    @app.get("/api/connections/{provider}/callback")
    def callback(provider: Provider, background: BackgroundTasks, state: str = "", code: str = "",
                 error: str = "", session: str = Depends(require)):
        if provider == "bennett" or not providers.available(provider) or len(state) > 100:
            raise HTTPException(400, "Invalid provider callback")
        stored = store.consume_state(state, provider, session)
        if stored is None:
            raise HTTPException(400, "OAuth state expired or did not match. Start again in Settings.")
        if error or not code or len(code) > 4096:
            return RedirectResponse("/?connection=declined#settings", status_code=303)
        try:
            providers.complete(provider, code, stored["verifier"])
        except ProviderError:
            return RedirectResponse("/?connection=failed#settings", status_code=303)
        background.add_task(providers.sync, provider)
        return RedirectResponse("/?connection=connected#settings", status_code=303)

    @app.post("/api/connections/{provider}/sync", dependencies=secure)
    def sync(provider: Provider):
        if not providers.available(provider) or not store.connection(provider):
            raise HTTPException(409, "Connect the source first")
        providers.sync(provider)
        return status()[provider]

    @app.delete("/api/connections/{provider}", dependencies=secure)
    def disconnect(provider: Provider):
        store.disconnect(provider)
        return {"ok": True}

    if DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")
        @app.get("/{path:path}", include_in_schema=False)
        def frontend(path: str):
            if path.startswith("api/"):
                raise HTTPException(404)
            if path in {"sw.js", "manifest.webmanifest", "daymark.svg", "icon-192.png", "icon-512.png"}:
                return FileResponse(DIST / path, headers={"Cache-Control": "no-cache"})
            if path:
                raise HTTPException(404)
            return FileResponse(DIST / "index.html", headers={"Cache-Control": "no-cache"})
    else:
        @app.get("/")
        def missing_build():
            return {"detail": "Run npm --prefix frontend ci and npm --prefix frontend run build."}

    return app


app = create_app()
