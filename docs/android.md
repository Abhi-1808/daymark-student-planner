# Daymark on your Android phone

Daymark currently has one personal workspace. Install its web app from Chrome on
Android; your computer keeps the database and connected source credentials, and
continues importing calendars. No multi-user accounts or public hosting are needed.

Keep the computer awake with Daymark running for live data, editing and syncing.
After a successful visit, the installed app can show its last saved calendar and
study data when the computer is off. Offline editing and background phone syncing
are not supported. This is an installed web app, not an APK or a Play Store release.

## 1. Prepare the computer

Use the normal Python environment with `requirements.lock` installed using
`python -m pip install --require-hashes --only-binary=:all: -r requirements.lock`.
From the project root, build the frontend:

```powershell
Set-Location Frontend
npm.cmd ci
npm.cmd run build
Set-Location ..
```

Leave `VITE_API_URL` unset for this build. In particular, remove a desktop-only
override from `Frontend/.env.local` before building for your phone. The compiled
app uses the same HTTPS address for its frontend and API. Vite's development and
preview ports still use the desktop backend on port 8000.

For computer-only use, start the compiled app and API together:

```powershell
python scripts/run_local.py
```

Open **http://127.0.0.1:8000**. This replaces the separate backend and Vite preview
servers. Stop an older backend with Ctrl+C in its own terminal before starting
another one against the same database. Use exactly one worker; startup now refuses
a second Daymark process using the same database. Automatic sync stops with this
process. Source sign-ins still open in the computer's browser.

## 2. Connect your own devices privately

Install [Tailscale](https://tailscale.com/download) on the computer and Android
phone. Sign in to the same personal account on both and connect both devices.
Tailscale must remain connected on the phone whenever it needs live Daymark data.

Stop the computer-only Daymark process, then run from the project root:

```powershell
python scripts/run_local.py --phone
```

The launcher reads the connected computer's Tailscale status, selects its owner
login and HTTPS DNS name, and prints a phone address such as
`https://your-computer.your-tailnet.ts.net`. It does not publish anything itself.
Once the server has started successfully, open another terminal and run:

```powershell
tailscale serve --bg http://127.0.0.1:8000
```

On Windows, the launcher uses the standard `Program Files\Tailscale\tailscale.exe`
installation and does not accept an executable found earlier on PATH. The locally
installed CLI and operating system remain trusted, like the Daymark process itself.
The launcher logs the absolute executable path as `daymark.phone.cli_resolved`.
Path resolution identifies what will run; it does not verify the binary's publisher
or signature. The CLI's status JSON is not written to that log event.

If Tailscale is not on PATH, run its full Windows path instead:

```powershell
& 'C:\Program Files\Tailscale\tailscale.exe' serve --bg http://127.0.0.1:8000
```

Complete the HTTPS enablement link if Tailscale displays one. Use **Serve**, which
keeps access inside your private network. Do not enable Funnel or router port
forwarding. Restrict your tailnet to devices you trust.

The backend stays bound to `127.0.0.1`. Private requests must come through the
local Serve proxy, use the configured HTTPS host, and carry the exact owner login
inserted by Tailscale. Missing or different identities receive 403, including
another person with a shared device. Raw network requests are rejected even if
they forge the identity header. The launcher disables forwarded-IP trust so these
checks use the real socket peer. Trust local processes on the computer.

The supported private proxy is Tailscale Serve. Its identity headers are not a
general-purpose authentication protocol for arbitrary reverse proxies. See the
[official identity-header documentation](https://tailscale.com/docs/features/tailscale-serve#identity-headers).
Computer-only mode rejects forwarded requests too, so an old Serve mapping does
not grant access after restarting without `--phone`.

For a different port, use `--port 8123` and change Serve's target to
`http://127.0.0.1:8123`. Do not point Serve at an older, unconfigured backend or at
Vite's preview server. Always restart phone access with `--phone`; Serve's mapping
persists after stopping Daymark.

To stop private sharing:

```powershell
tailscale serve --https=443 off
```

## 3. Install on Android

1. With Tailscale connected, open the printed **HTTPS** phone address in Chrome.
2. Wait for your timetable and the saved-for-offline status to appear.
3. In Chrome's menu choose **Install app**, or **Add to Home screen → Install**.
4. Open Daymark from its new home-screen icon.

The manifest includes 192px and 512px PNG icons. Each production build gets its own
service-worker cache version; API and sign-in responses are never cached by the
worker. Existing calendar/study snapshots remain separate in IndexedDB and are
replaced on successful reloads. The same workspace is shared between your two
devices, while display preferences and offline snapshots are saved per browser.

Manage Google, Microsoft/MyCamu and LMS sign-ins on the computer. The phone can
request syncs and use the connected data; it cannot launch desktop sign-in windows.

## Checks and limitations

- `/health` returns HTTP 200 only when the database is readable and the expected
  scheduler is running with its sync job; otherwise it returns 503. Intentionally
  disabled automatic syncing is healthy. This endpoint does not call providers;
  inspect Profile for their most recent sync results.
- SQLite uses WAL mode and a five-second busy timeout. Shut Daymark down before
  manually copying its database, or use SQLite's backup API; copying only the main
  file while WAL writes are active can omit recent changes.
- The local launcher uses one worker and structured JSON logs. Request logs include
  request IDs, route templates, status and duration, excluding URL query strings.
- The compiled app blocks inline scripts and unneeded device permissions, suppresses
  referrers, and restricts script/API loading to its own address. Keep `VITE_API_URL`
  unset for this setup. API docs allow only their own initializer hashes and CDN assets.
- Study history is retained. Use `scripts/sync_report.py` on saved logs to count
  source failures over a chosen period without uploading calendar data.
- This remains one person's workspace. Separate user accounts, per-user credentials
  and authorization would be a separate project before any shared public service.
- Laptop sleep, internet loss, expired source sign-ins and a disconnected phone VPN
  can interrupt live sync. Frontend installation does not turn the laptop backend
  into an Android background service.

The production build, desktop Chrome and simulated phone requests can be checked
without your phone. The actual Android install and the real Tailscale connection
still need to be verified on your devices after you connect them.

References: [Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve)
and [web app manifests](https://web.dev/articles/add-manifest).
