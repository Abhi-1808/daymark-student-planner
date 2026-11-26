# Daymark setup

## Private configuration

Copy `.env.example` to `.env` in the repository root if you need a password or an integration. Restart the server after changing it. Use the same browser origin everywhere, including the scheme, host, and port. The local instructions use `http://localhost:8000`.

Generate one token encryption key and save it in `DAYMARK_TOKEN_KEY`.

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Keep `.env` private. Keep the encryption key with any private database backup if you want to restore existing connections. If the key is lost, reconnect the providers with a new key.

## Google Calendar and Tasks

1. In Google Cloud, create or select a project, then enable **Google Calendar API** and **Google Tasks API**.
2. Configure the OAuth consent screen. If the app is in testing, add your Google account as a test user.
3. Create an OAuth client of type **Web application**. Register `http://localhost:8000/api/connections/google/callback` as an authorized redirect URI. For another origin, replace the localhost prefix with `DAYMARK_ORIGIN`.
4. Set `DAYMARK_GOOGLE_CLIENT_ID` and `DAYMARK_GOOGLE_CLIENT_SECRET` in `.env`.
5. Restart, open **Settings → Connected accounts → Google → Connect**, and approve read-only access. Use **Sync now** to check the initial import.

The app requests `calendar.calendarlist.readonly`, `calendar.events.readonly`, and `tasks.readonly`. Some testing configurations expire refresh tokens and require reconnecting.

[Google OAuth web-server setup](https://developers.google.com/identity/protocols/oauth2/web-server) · [Google API scopes](https://developers.google.com/identity/protocols/oauth2/scopes)

## Microsoft Outlook

1. Register a Microsoft Entra application. Select the supported account type that matches the account you plan to use.
2. Add a **Web** redirect URI of `http://localhost:8000/api/connections/microsoft/callback`, using the configured origin if it differs.
3. Add Microsoft Graph delegated `Calendars.ReadBasic` and allow `offline_access`. A university tenant may require administrator consent.
4. Add a client secret and set `DAYMARK_MICROSOFT_CLIENT_ID` and `DAYMARK_MICROSOFT_CLIENT_SECRET`. Keep `DAYMARK_MICROSOFT_TENANT=common` for an app that supports the relevant multiple account types, or use the tenant ID for a single-tenant registration.
5. Restart and choose **Settings → Connected accounts → Microsoft Outlook → Connect**.

To use email reminders, add the delegated `Mail.ReadBasic` permission, set `DAYMARK_MICROSOFT_MAIL=1`, restart, and reconnect. Use **Outlook inbox reminders** to read up to 25 recent headers and select a message to create a local task. Daymark does not fetch message bodies or send email.

[Microsoft authorization code flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow) · [CalendarView permissions](https://learn.microsoft.com/en-us/graph/api/user-list-calendarview?view=graph-rest-1.0) · [List messages](https://learn.microsoft.com/en-us/graph/api/mailfolder-list-messages?view=graph-rest-1.0)

## Bennett LMS and MyCamu

Open the [Bennett LMS](https://lms.bennett.edu.in/) calendar. If your account shows **Export calendar**, choose the course events and date range you want, then download the ICS file or copy its subscription link. Import the file as **Bennett LMS** in Settings. To sync automatically, put your own export link in `DAYMARK_BENNETT_ICS`. The link must use `https://lms.bennett.edu.in/calendar/export_execute.php` with its query string. Keep the entire link private.

[Calendar export guide](https://docs.moodle.org/en/Using_Calendar#Calendar_export)

For **MyCamu**, use an authorized timetable file if you have one, or copy your classes into the CSV format below. In Settings, import it as MyCamu. For scheduled refresh, set `DAYMARK_CAMU_FILE` to the path of your CSV or ICS file on the Daymark host. Update that file when your timetable changes. This connection follows the file and does not sign into MyCamu.

Automatic sync defaults to five minutes. `DAYMARK_SYNC_SECONDS=0` disables scheduled refresh and leaves **Sync now** available. Outlook, Google Calendar, and recurring ICS imports use a rolling window from 60 days back through the next 365 days. A new successful sync replaces each provider's previous snapshot. A failed sync preserves the last data and displays the error in Settings.

## CSV format

Use UTF-8. The only shared required columns are `kind` and `title`. Events need start and end, and attendance entries need a date and subject code. Date-only event ends are exclusive, so a one-day holiday on the 27th ends on the 28th. A timed value with no explicit offset uses your planning time zone. A stable `external_id` lets a new import update the matching row from the same source.

```csv
kind,title,course,start,end,due,category,attendance,external_id
course,Database Systems,CSE245,,,,personal,,subject-cse245
event,Database Systems lecture,CSE245,2026-11-27T09:00,2026-11-27T10:00,,class,,lect-1127
task,Submit SQL assignment,CSE245,,,2026-11-30,assignment,,sql-assignment
attendance,Database Systems lecture,CSE245,,,2026-11-27,personal,present,att-1127
```

Other supported columns include `minutes`, `priority`, `notes`, `location`, `repeat` (`none`, `daily`, or `weekly`), `repeat_until`, `color`, `target`, `done`, and `busy`. Use numbers for estimates and attendance targets. CSV and ICS uploads are limited to 2 MB. Imported records are read-only and you can make local editable copies from their details.

For a full backup, stop Daymark and securely copy the database and relevant private configuration. CSV is for interchange and does not preserve OAuth sessions, source settings, or the editable status of the originals.

## Private phone access

Keep the backend listening on `127.0.0.1:8000`. On a host with Tailscale, use [Tailscale Serve](https://tailscale.com/kb/1242/tailscale-serve) in your private tailnet to proxy the local backend over HTTPS.

```bash
tailscale serve --bg http://127.0.0.1:8000
```

Set `DAYMARK_ORIGIN` to the exact HTTPS address reported by Tailscale, set a unique `DAYMARK_PASSWORD` of at least 12 characters, and restart the backend. Register the HTTPS callbacks for any connected providers. Open the HTTPS address on your phone with Tailscale active and use your browser's install or home-screen action. Keep the host running to sync or make changes.
