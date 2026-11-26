import { useMemo } from 'react'
import { ArrowRight, CalendarDays, CircleAlert, ClipboardList, Compass, LayoutGrid, Plus } from 'lucide-react'
import { addDays, categories, dateLabel, expand, freeSlots, includesDay, slotMinutes, taskOrder, timeLabel, weekStart } from './planner.js'
import { Empty, EventRow, SectionTitle, TaskRow } from './ui.jsx'

export function Today({ workspace, visibleRecords, today, nav, setDay, open, toggle, create, sample, canEdit, now }) {
  const prefs = workspace.preferences
  const zone = prefs.timezone
  const { week, markedDays, events, nextTasks, upcoming } = useMemo(() => {
    const firstDay = weekStart(today)
    const week = Array.from({ length: 7 }, (_, index) => addDays(firstDay, index))
    const items = expand(visibleRecords, addDays(firstDay, -1), addDays(today, 30), zone)
    const events = []
    const due = []
    const upcoming = []
    const markedDays = new Set()
    for (const item of items) {
      if (item.kind === 'event') {
        for (const day of week) if (includesDay(item, day)) markedDays.add(day)
        if (includesDay(item, today)) events.push(item)
        if (item.date > today && ['exam', 'assignment', 'class'].includes(item.category)) upcoming.push(item)
      } else if (item.kind === 'task' && item.date >= today && item.date <= week[6] && !item.done) {
        due.push(item)
      }
    }
    const undated = visibleRecords.filter(item => item.kind === 'task' && !item.due && !item.done)
    const nextTasks = [...taskOrder(due), ...undated].slice(0, 4)
    return { week, markedDays, events, nextTasks, upcoming: upcoming.slice(0, 3) }
  }, [today, visibleRecords, zone])
  const existing = useMemo(() => expand(workspace.records, addDays(today, -1), addDays(today, 1), zone), [workspace.records, today, zone])
  const slots = useMemo(() => freeSlots(existing, today, prefs, now), [existing, today, prefs, now])
  const minutes = slotMinutes(slots)
  const duration = minutes >= 60 ? `${Math.floor(minutes / 60)}h${minutes % 60 ? ` ${minutes % 60}m` : ''}` : `${minutes}m`

  return <div className="today-view">
    <header className="page-heading today-heading">
      <div><h1>Today</h1>
        <p className="day-label">{dateLabel(today, { weekday: 'long', month: 'long', day: 'numeric' })}</p>
        <p>{duration} free today</p></div>
      <button className="button secondary" onClick={() => { setDay(today); nav('calendar') }}><CalendarDays size={16} /> Open calendar</button>
    </header>
    {!workspace.records.length && canEdit && <div className="onboard">
      <div className="onboard-icon"><Compass size={21} /></div><div><strong>Set up your first day</strong><p>Add a class or a deadline, import a calendar, or explore with example data.</p></div>
      <div className="inline"><button className="button secondary" onClick={sample}>Load sample data</button><button className="button primary" onClick={() => create('event')}><Plus size={16} /> Add event</button></div>
    </div>}
    <div className="grid items-start gap-4 min-[721px]:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
      <section className="panel schedule-panel">
        <SectionTitle title="Schedule" />
        <div className="week-strip">{week.map(day => <button key={day} aria-label={dateLabel(day, { weekday: 'long', month: 'long', day: 'numeric' })} aria-current={day === today ? 'date' : undefined}
          onClick={() => { setDay(day); nav('calendar', 'day') }} className={day === today ? 'current' : ''}>
          <span>{dateLabel(day, { weekday: 'short' })}</span><strong>{Number(day.slice(-2))}</strong>
          <i className={markedDays.has(day) ? 'marked' : ''} />
        </button>)}</div>
        <div className="schedule-list">
          {events.length ? events.map(item => <EventRow key={item.key} item={item} zone={zone} onClick={() => open(item)} />)
            : <Empty title="Your schedule is clear"
              action={canEdit && <button className="text-button" onClick={() => create('event')}><Plus size={16} /> Add event</button>} />}
        </div>
      </section>
      <section className="panel tasks-panel">
        <SectionTitle title="Tasks" action="All tasks" onAction={() => nav('tasks')} />
        <div className="task-list">{nextTasks.map(item => <TaskRow key={item.key || item.id} item={item} today={today}
          onOpen={() => open(item)} onToggle={canEdit && item.source === 'manual' ? () => toggle(item) : null} compact />)}
          {!nextTasks.length && <Empty icon={ClipboardList} title="No upcoming tasks"
            action={canEdit && <button className="text-button" onClick={() => create('task')}><Plus size={16} /> Add task</button>} />}</div>
        <div className="plan-prompt">
          {slots.length > 0 && <p>Next free slot at {timeLabel(slots[0].start, zone)}</p>}
          <button className="text-button" onClick={() => nav('study')}>Plan study time <ArrowRight size={15} /></button>
        </div>
      </section>
    </div>
    {!!upcoming.length && <section className="panel upcoming-panel">
      <SectionTitle title="Coming up" action="Browse calendar" onAction={() => nav('calendar')} />
      <div className="upcoming-grid">{upcoming.map(item => <button key={item.key} onClick={() => open(item)} className="upcoming-item">
        <span className={`metric-icon ${item.color}`}>{item.category === 'exam' ? <CircleAlert size={18} /> : <LayoutGrid size={18} />}</span>
        <span><strong>{item.title}</strong><small>{dateLabel(item.date)} · {categories[item.category]}</small></span></button>)}</div>
    </section>}
  </div>
}
