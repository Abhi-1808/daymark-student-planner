# What changed in Daymark, and why

This page explains the project's history in plain language. No programming
knowledge is needed. Each section answers three questions: what was wrong, what
we did, and what it means for you when you use the app.

---

## First, what Daymark is

Daymark is a personal planner for university students. It brings four things
into one screen:

1. **Your classes** — from MyCamu and the Bennett LMS.
2. **Your deadlines and appointments** — from Google Calendar and Google Tasks.
3. **Your own to-do list** — tasks you add yourself.
4. **Your Outlook meetings and email follow-ups** — from your Bennett account.

It then helps you find time to study around your classes, meetings and other
calendar commitments, and keeps notes for each subject.

Everything runs on **your own computer**. Nothing is uploaded to a company. Your
Google, university and Outlook calendars are only ever _read_ by Daymark's sync.
Planning in Daymark does not change those source calendars.

---

## The big idea behind all the work

Daymark started as one large file that did almost everything. That works for a
small experiment, but it is hard to check, hard to fix, and easy to break in
places you are not looking.

Most of the work since then has been **tidying the inside of the app** so that:

- each part does one job,
- each part can be tested on its own,
- changing one part cannot quietly break another.

None of that is visible on screen. That is the point. A tidy inside means the
features you use stop breaking unexpectedly.

---

## Stage 1 — Splitting the giant file into smaller parts

**What was wrong.** One file handled the database, the sign-ins, the syncing and
the web addresses, all at once. Importing it just to run a test would also
change the database.

**What we did.** We broke it into small files, each with a clear name: one for
the database setup, one for importing items, one for deciding what each
calendar source is allowed to do, and one for sign-in redirects.

**What it means for you.** Problems are now easier to find, and a mistake in one
area is far less likely to affect another.

---

## Stage 2 — One shared way to find free study time

**What was wrong.** The daily planner and the exam revision planner each had
their own copy of the same logic — where to put a 45-minute study block, and
where to leave a 5-minute break. If one was fixed, the other stayed broken.

**What we did.** Both now use one shared piece of code. We also fixed a real
bug: study blocks that ran past midnight lost their breaks.

**What it means for you.** Study plans behave the same way everywhere, and the
breaks between study blocks are protected even across midnight.

---

## Stage 3 — Pop-up windows that all behave the same way

**What was wrong.** The app has several pop-up windows: the item editor, the
quick-add box, the duplicate review, the MyCamu sign-in and the LMS sign-in.
Each had its own separate code for handling the keyboard — so they behaved
differently. In some, pressing Tab could move focus outside the window. In
others, it could not.

**What we did.** One shared system for all of them. It handles closing with
Escape, keeps the keyboard focus inside the window, and returns you to the
button you started from when the window closes. It also works when one pop-up
opens on top of another.

**What it means for you.** If you use a keyboard, the app now behaves the same
everywhere. That matters even more on a phone with a Bluetooth keyboard.

---

## Stage 4 — A simpler main screen

**What was wrong.** The main application screen had grown to hold around twenty
separate pieces of information at once, plus the code for syncing and for
duplicate review. Reading it was exhausting and testing it was impossible.

**What we did.** We moved that logic into small, named helpers: one for which
screen you are looking at and what filters are on, one for syncing, one for
duplicate review, and one for checking sync status in the background.

**What it means for you.** Each area can now be tested independently. The screen
also stopped doing unnecessary work — for example, it no longer re-scans your
entire task list every time you type a letter into the search box.

---

## Stage 5 — One clear look and feel

**What was wrong.** The app carried several generations of colour schemes at
once, left behind from earlier versions. Later styles won, but the old ones were
still shipped, so it was confusing to know which colours were real. The fonts
the styles asked for were never loaded, so headings quietly fell back to a
different font than intended.

**What we did.** We created one single place that defines every colour and font,
and made everything else read from it. IBM Plex Sans is bundled with the app,
so the font works offline without downloading it from another website.

**What it means for you.** The app looks consistent, and there is now one place
to change if a colour ever needs updating.

---

## Stage 6 — Fewer downloads, same information

**What was wrong.** Every time the app refreshed — after saving a task, after a
sync, or every ten seconds — it downloaded _your entire study history_. After a
year, that is a lot of data to send repeatedly, especially to a phone.

**What we did.** The app now asks only for a sensible range of dates: about
three months back and three months forward. Behind the scenes it still keeps
your full history and still counts your previously planned study time
correctly, so nothing gets planned twice.

**What it means for you.** Faster loading, less data used on your phone, and no
change to what you see.

---

## Stage 7 — Using it on your phone, privately

**What was wrong.** The app ran only on the laptop. There was no safe way to open
it from a phone without putting it on the public internet, which we did not
want.

**What we did.** Added an optional private mode that works through Tailscale, a
trusted private network tool you install yourself. Your computer stays the
server. Only your own signed-in devices can reach it. Requests arriving by any
other route are refused outright.

On Windows, the phone setup finds Tailscale in its fixed installation folder
rather than wherever the system happens to look first. This stops a wrongly
placed program from answering in Tailscale's place.

Your sign-ins stay on the computer. The phone can _look_ at your data and ask
for a refresh, but it cannot start a browser sign-in window.

**What it means for you.** You can check your day from your phone, and your
computer needs to be switched on and awake for live information. The app still
shows the last saved copy when it cannot reach the computer.

**Please note.** The Android installation itself has **not yet been tested on a
real phone**. That is still to do.

---

## Stage 8 — Health checks that can actually fail

**What was wrong.** The app's health address always answered "everything is
fine," even if the database was locked or the automatic syncing had stopped.

**What we did.** The health check now actually looks at the database and at the
background sync. If either is broken, it says so.

We also added a guard that prevents two copies of Daymark running against the
same database — previously that could cause two syncs at once and get your
accounts temporarily blocked.

**What it means for you.** Problems show up as problems instead of silence, and
it is harder to accidentally run the app twice.

---

## Stage 9 — Exact versions, so installs stop drifting

**What was wrong.** The list of required software used loose version ranges, so
installing the app today and again in six months could produce two different
setups. That makes "it worked on my machine" very likely.

**What we did.** We locked the exact versions with fingerprints, in a separate
file. Installing now verifies every package matches what we recorded.

**What it means for you.** If it installs successfully once, it will install the
same way next time.

---

## Stage 10 — Small safety touches

- **Browser security rules** tell the browser to refuse unexpected connections,
  so if anything were ever injected into the page it could not send your data
  somewhere else.
- **Log messages** now use a fixed name for sync failures, so the number of
  failures can be counted instead of guessed at by reading prose.
- **Logs never contain your passwords or tokens.** Even when an error is
  recorded, the private details are left out.

---

## Stage 11 — Outlook meetings and chosen email reminders

**What was wrong.** Meetings and emails that needed a follow-up lived in Outlook,
separate from the planner. The first direct Microsoft connection required
university administrator approval.

**What we did.** Linked Daymark to the Bennett account already signed into Classic
Outlook on Windows. It reads meeting details and recent email subjects and senders,
without downloading message bodies or attachments or changing Outlook records.
An email becomes a task only when you choose it and confirm a reminder.

**What it means for you.** Meetings appear alongside your classes, invitations
appear in Today, and chosen email reminders appear in Tasks. With automatic
syncing enabled, Daymark checks Outlook's saved information every five minutes
by default. Keep Classic Outlook open and online, and Daymark running on an awake
computer, so new mail and meetings can reach it. Device alerts are optional and
work while Daymark is open. The separate direct Microsoft connection still needs
university approval; using Classic Outlook does not grant that access.

---

## What has been checked, and what has not

**Automated checks (run locally):**

- The back-end logic.
- The on-screen behaviour.
- The packaging scripts.
- A full production build.
- An automated browser run that uses fake sample data, so your real calendars
  and accounts are never touched.

These checks can be run again, but do not run automatically on every local edit.
The browser checks do not sign in to live accounts.

**One-time live check — 4 November 2026:**

Classic Outlook imported 2 calendar entries, 50 recent email headers and
2 meeting-request emails. This was observed once against the signed-in Bennett
account, separately from the automated checks. It has not been repeated for this
documentation update.

**Not yet checked — please do not assume these work:**

1. **The actual installation on your Android phone, real daily use and notification
   delivery.** This needs your two devices connected.
2. **A run on GitHub's own test servers.** The automatic testing setup is
   written and saved, but it has never run there, because the project has not
   been uploaded to GitHub yet.

---

## A note on your study history

Study sessions are kept forever, on purpose. Daymark uses them to know how much
time you have already put into a task. If old records were deleted, the planner
would forget that work and could offer you the same study time again.

There is no automatic clean-up. If the list ever becomes very large, the right
answer is to summarise old entries into a total, not to delete them — and only
after careful testing.
