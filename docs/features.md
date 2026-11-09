# Using Daymark

Navigate between **Today**, **Calendar**, **Tasks**, **Study**, and **Settings**
in the sidebar. **Create** opens a menu for a new event/task or natural-language
Quick Add. Search stays in the header. The sidebar and Upcoming panel can be
collapsed independently; these preferences stay in your browser.

Click a date or empty space in a month-calendar cell to open its day schedule.
The Day view shows an hourly timeline, overlapping events side by side, all-day
items, scheduled work sessions, and tasks due that day. Use the previous/next
buttons or date picker to move between days, **Month** to return, and
**Create > Event or task** to create something on the selected date.
Day, Week and Month share the calendar toolbar. **Filters** contains item types
and source visibility; its count shows when display filters are active.

Existing events and tasks open in a view with their dates, source, notes and
task details. Choose **Edit event** or **Edit task** to make local changes.
**Cancel** discards the draft and returns to the details. Imported items offer
**Change priority** for the local preference; their source-managed details remain
read-only. Offline copies stay viewable with editing disabled. New items open
directly in the creation form.

The small sync indicator opens refresh actions and **Manage connections**.
Source connection details live in **Settings**. Duplicate suggestions appear in
the **Review** badge so they do not obstruct the calendar.

Duplicate checking compares MyCamu and Google Calendar events with identical
dates and start/end times, similar subject names, and matching rooms when both
are supplied. Room and lecture/practical labels are normalized for matching.
Manual items, tasks, different course levels, and conflicting rooms are excluded.
Use **Review** to inspect the suggested pairs, select
which Google Calendar copies to remove, and explicitly confirm. Detection and
syncing never approve a removal automatically.

Removal hides only the selected copies in Daymark; the original source calendars
are not changed. Use **Undo** or **Review → Removed → Restore** to bring them
back. Unchanged source refreshes preserve approved removals. If a class changes
so that the two copies are no longer duplicates, the hidden copy becomes visible
again. Confirmation also checks that the reviewed events have not changed.

In **Today → Make today's plan**, choose the tasks you want to work on and
select **Preview today's plan**. Check the proposed times, then choose **Add
study blocks to calendar**. Going back to the task list adds nothing.

The planner uses campus time, your saved study hours and time around classes.
You can change the hours for a single plan. It subtracts work already scheduled,
splits longer tasks into blocks of up to 45 minutes with short breaks, and explains
work that cannot fit before its deadline today. Every calendar source still counts
as busy time. A preview lasts five minutes; calendar/task changes require a fresh
review, and a confirmed preview can only be added once. Tasks remain unfinished
until you tick them off. Due dates and study blocks are separate.


## Study tools and offline app

The implemented roadmap is tracked in [TODO.md](../TODO.md).

- **Week** shows Monday through Sunday with hourly classes and study sessions,
  plus a separate deadline/all-day row. Select a date heading to open that day.
- **Filters > sources** temporarily hides individual imports. These preferences persist
  in the browser; hidden sources still block study time and no events are deleted.
- **Study > Study time** provides timetable checks, task suggestions that fit
  your current gap, and a comparison of needed work with free time. Use **Plan
  today** to open the daily planner. Usual study hours and time around classes
  are under an expandable settings row. Matching Google/MyCamu copies are ignored for conflict
  analysis while both remain stored. The workload calculation also flags deadlines
  with insufficient time even when the whole week has spare capacity.
- **Subjects** groups known classes and lets you add subjects, save personal notes
  and useful links, and add related tasks or classes. Upcoming items appear first;
  **Include past items** opens earlier history. Notes live in SQLite and are
  independent of external source refreshes.
- **Attendance** saves manual per-subject counts and a user-selected target.
  Future attendance/missed-class scenarios are previews; they do not alter counts.
  Calendar presence is never treated as proof of attendance.
- **Exam prep** guides you through the exam date, topic rows and study estimates,
  then shows a preview. It also accepts an existing calendar event. Preview spreads
  revision across free days, preserves classes and sessions, and reports work that
  cannot fit. Nothing is scheduled until **Confirm and add**. Previews expire in
  five minutes and are rejected if the calendar changed; repeat confirmation
  cannot add duplicate revision sessions.

Each Study tab explains its purpose and has **How to use this tool** instructions.
Attendance shows an example of which counts to enter and keeps future scenarios
separate from saved records.
- **Quick add** understands today, tomorrow, weekdays, `in 3 days`, ISO dates,
  AM/PM or 24-hour times, `for 45m` / `for 1h 30m`, and a final `p1`, `p2` or `p3`.
  It always shows an editable preview before creating a manual task. Missing
  dates/times are labeled explicitly, and ambiguous times require clarification.
- **Offline viewing** saves the last successfully loaded calendar, study notes and
  exams in browser storage. The service worker caches frontend assets only;
  authentication/API responses are not stored in its asset cache. Offline views
  show their last-loaded timestamp, disable mutations and never replay writes.
  Reconnect reloads current data. Use **Install Daymark** when offered by your browser.

The PWA works on localhost and supports HTTPS deployment. Phone access requires a
reachable backend and secure hosting; installing the frontend alone does not expose
this laptop's localhost server. Keep one backend running for source refreshes.

New local APIs are `GET /api/study/subjects`, `PUT /api/study/subjects/{key}`,
`GET/POST /api/study/exams`, `POST /api/study/exams/{id}/preview`, and
`POST /api/study/exams/{id}/plan`.
