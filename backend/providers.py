import base64
import hashlib
import json
import re
import threading
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode, urlsplit
from zoneinfo import ZoneInfo

import httpx
from cryptography.fernet import Fernet, InvalidToken

from .models import Record
from .transfer import bounds, identity, parse_ics, text_value


class ProviderError(Exception):
    pass


class Providers:
    def __init__(self, config, store, transport=None):
        if not re.fullmatch(r"[A-Za-z0-9.-]+", config.microsoft_tenant):
            raise RuntimeError("DAYMARK_MICROSOFT_TENANT is invalid")
        self.config = config
        self.store = store
        self.cipher = Fernet(config.key) if config.key else None
        self.locks = {name: threading.Lock() for name in ("google", "microsoft", "bennett")}
        self.transport = transport
        self.bennett_url = config.bennett_url
        if self.bennett_url:
            url = urlsplit(self.bennett_url)
            if (url.scheme, url.netloc, url.path) != ("https", "lms.bennett.edu.in", "/calendar/export_execute.php"):
                raise RuntimeError("DAYMARK_BENNETT_ICS must be the HTTPS calendar export URL from Bennett LMS")
            if not url.query or url.fragment:
                raise RuntimeError("DAYMARK_BENNETT_ICS requires the calendar export query")

    def available(self, provider):
        if provider == "bennett":
            return bool(self.bennett_url)
        args = self.oauth_config(provider)
        return bool(self.cipher and args["client_id"] and args["client_secret"])

    def oauth_config(self, provider):
        if provider == "google":
            return {
                "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
                "token": "https://oauth2.googleapis.com/token",
                "client_id": self.config.google_id,
                "client_secret": self.config.google_secret,
                "scope": "https://www.googleapis.com/auth/calendar.calendarlist.readonly https://www.googleapis.com/auth/calendar.events.readonly https://www.googleapis.com/auth/tasks.readonly",
            }
        authority = f"https://login.microsoftonline.com/{self.config.microsoft_tenant}/oauth2/v2.0"
        return {
            "authorize": f"{authority}/authorize", "token": f"{authority}/token",
            "client_id": self.config.microsoft_id, "client_secret": self.config.microsoft_secret,
            "scope": "offline_access https://graph.microsoft.com/Calendars.ReadBasic",
        }

    def callback(self, provider):
        return f"{self.config.origin}/api/connections/{provider}/callback"

    def authorization(self, provider, state, verifier):
        settings = self.oauth_config(provider)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        params = {
            "client_id": settings["client_id"], "redirect_uri": self.callback(provider),
            "response_type": "code", "scope": settings["scope"], "state": state,
            "code_challenge_method": "S256", "code_challenge": challenge,
        }
        if provider == "google":
            params.update(access_type="offline", prompt="consent")
        return settings["authorize"] + "?" + urlencode(params)

    def seal(self, token):
        return self.cipher.encrypt(json.dumps(token).encode()).decode()

    def token(self, provider, **params):
        settings = self.oauth_config(provider)
        try:
            with self.client() as client:
                response = client.post(settings["token"], data={
                    "client_id": settings["client_id"], "client_secret": settings["client_secret"], **params,
                })
                response.raise_for_status()
                token = response.json()
            if not token.get("access_token"):
                raise ValueError("Missing access token")
            token["expires_at"] = datetime.now(timezone.utc).timestamp() + int(token.get("expires_in", 3600))
            return token
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as error:
            raise ProviderError("Provider authorization failed. Check your registration and consent, then reconnect.") from error

    def complete(self, provider, code, verifier):
        token = self.token(provider, grant_type="authorization_code", code=code,
                           code_verifier=verifier, redirect_uri=self.callback(provider))
        if not token.get("refresh_token"):
            raise ProviderError("Provider did not issue a refresh token. Allow offline access and reconnect.")
        self.store.connect(provider, self.seal(token))

    def client(self, **kwargs):
        return httpx.Client(follow_redirects=False, timeout=18, transport=self.transport, **kwargs)

    def sync(self, provider):
        with self.locks[provider]:
            connection = self.store.connection(provider)
            if not connection or not self.available(provider):
                return
            encrypted = connection["token"]
            updated_token = encrypted
            zone = ZoneInfo(self.store.snapshot()["preferences"]["timezone"])
            safe_error = None
            try:
                if provider == "bennett":
                    feeds = {"bennett-feed": self.bennett_events(zone)}
                else:
                    token = json.loads(self.cipher.decrypt(encrypted.encode()))
                    if token["expires_at"] < datetime.now(timezone.utc).timestamp() + 120:
                        refresh = token["refresh_token"]
                        token = self.token(provider, grant_type="refresh_token", refresh_token=refresh)
                        token.setdefault("refresh_token", refresh)
                        updated_token = self.seal(token)
                    with self.client(headers={"Authorization": f"Bearer {token['access_token']}"}) as client:
                        feeds = self.google(client, zone) if provider == "google" else self.microsoft(client, zone)
            except ProviderError as error:
                safe_error = str(error)
            except (httpx.HTTPError, KeyError, ValueError, InvalidToken, TypeError, AttributeError, OverflowError):
                safe_error = "Sync failed. Your previous data is still available. Check the connection and try again."
            now = datetime.now(timezone.utc).isoformat()
            self.store.finish_sync(provider, encrypted, updated_token, feeds if not safe_error else {},
                                   now if not safe_error else None, safe_error)

    def bennett_events(self, zone):
        with self.client() as client, client.stream("GET", self.bennett_url) as response:
            response.raise_for_status()
            payload = bytearray()
            for chunk in response.iter_bytes():
                payload.extend(chunk)
                if len(payload) > 2_000_000:
                    raise ProviderError("The Bennett calendar exceeds 2 MB.")
        return parse_ics(bytes(payload), zone, "bennett-lms")

    @staticmethod
    def pages(client, url, params=None, item_key="items"):
        host = urlsplit(url).netloc
        for _ in range(100):
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
            yield from payload.get(item_key, ())
            if payload.get("@odata.nextLink"):
                url, params = payload["@odata.nextLink"], None
                target = urlsplit(url)
                if target.scheme != "https" or target.netloc != host:
                    raise ProviderError("Provider returned an invalid pagination URL.")
            elif payload.get("nextPageToken"):
                params = {**(params or {}), "pageToken": payload["nextPageToken"]}
            else:
                return
        raise ProviderError("Provider returned too many pages. No changes were applied.")

    def google(self, client, zone):
        start, end = bounds(zone)
        api = "https://www.googleapis.com/calendar/v3"
        calendars = self.pages(client, f"{api}/users/me/calendarList", {"minAccessRole": "reader"})
        events = {}
        for calendar in calendars:
            calendar_id = quote(calendar["id"], safe="")
            for event in self.pages(client, f"{api}/calendars/{calendar_id}/events", {
                "timeMin": start.isoformat(), "timeMax": end.isoformat(),
                "singleEvents": "true", "maxResults": 2500,
            }):
                if event.get("status") == "cancelled":
                    continue
                first, last = event["start"], event["end"]
                events[identity(calendar_id, event["id"])] = event_record(
                    event.get("summary"), first.get("dateTime", first.get("date")),
                    last.get("dateTime", last.get("date")), event.get("location"),
                    event.get("transparency") != "transparent",
                )
        task_lists = self.pages(client, "https://tasks.googleapis.com/tasks/v1/users/@me/lists", {"maxResults": 100})
        tasks = {}
        for task_list in task_lists:
            list_id = quote(task_list["id"], safe="")
            for task in self.pages(client, f"https://tasks.googleapis.com/tasks/v1/lists/{list_id}/tasks", {
                "maxResults": 100, "showCompleted": "true", "showHidden": "true",
            }):
                if task.get("deleted"):
                    continue
                tasks[identity(list_id, task["id"])] = Record(
                    kind="task", title=text_value(task.get("title"), 200) or "Untitled task",
                    notes=text_value(task.get("notes"), 10000),
                    due=task["due"][:10] if task.get("due") else None,
                    done=task.get("status") == "completed",
                )
        return {"google-calendar": events, "google-tasks": tasks}

    def microsoft(self, client, zone):
        start, end = bounds(zone)
        base = "https://graph.microsoft.com/v1.0"
        client.headers["Prefer"] = 'outlook.timezone="UTC", IdType="ImmutableId"'
        outlook = {}
        calendars = self.pages(client, f"{base}/me/calendars", {"$select": "id"}, item_key="value")
        for calendar in calendars:
            calendar_id = quote(calendar["id"], safe="")
            events = self.pages(client, f"{base}/me/calendars/{calendar_id}/calendarView", {
                "startDateTime": start.isoformat(), "endDateTime": end.isoformat(), "$top": 200,
                "$select": "id,subject,start,end,location,isAllDay,isCancelled,showAs",
            }, item_key="value")
            for event in events:
                if event.get("isCancelled"):
                    continue
                first, last = (graph_time(event[key], event.get("isAllDay")) for key in ("start", "end"))
                outlook[identity(calendar_id, event["id"])] = event_record(
                    event.get("subject"), first, last, (event.get("location") or {}).get("displayName"),
                    event.get("showAs") != "free",
                )
        return {"outlook": outlook}


def graph_time(value, all_day):
    instant = datetime.fromisoformat(value["dateTime"])
    if not instant.tzinfo:
        instant = instant.replace(tzinfo=timezone.utc)
    if all_day:
        return (instant + timedelta(hours=12)).date().isoformat()
    return instant.isoformat()


def event_record(title, first, last, location, busy):
    if first == last:
        last = (datetime.fromisoformat(first) + timedelta(minutes=1)).isoformat()
    return Record(kind="event", title=text_value(title, 200) or "Untitled event",
                  start=first, end=last, location=text_value(location, 200), busy=busy, color="blue")
