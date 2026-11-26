import { ArrowRight, BookOpen, CalendarDays, CircleAlert, ClipboardList, Clock3, Compass, LayoutGrid, Plus } from 'lucide-react'
import { addDays, categories, dateLabel, expand, freeSlots, includesDay, slotMinutes, taskOrder, timeLabel, weekStart } from './planner.js'
import { Empty, EventRow, SectionTitle, TaskRow } from './ui.jsx'

function Metric({ icon: Icon, tint, value, label }) {
  return <div className="metric"><div className={`metric-icon ${tint}`}><Icon size={20} strokeWidth={1.8} /></div><div><strong>{value}</strong><span>{label}</span></div></div>
}

export function Today({ workspace, visibleRecords, today, nav, setDay, open, toggle, create, sample, canEdit, now }) {
  const prefs = workspace.preferences
  const zone = prefs.timezone
  const firstDay = weekStart(today)
  const week = Array.from({ length: 7 }, (_, index) => addDays(firstDay, index))
  const weekItems = expand(visibleRecords, addDays(firstDay, -1), week[6], zone)
  const events = weekItems.filter(item => item.kind === 'event' && includesDay(item, today))
  const due = taskOrder(weekItems.filter(item => item.kind === 'task' && item.date >= today && !item.done))
  const undated = visibleRecords.filter(item => item.kind === 'task' && !item.due && !item.done)
  const upcoming = expand(visibleRecords, today, addDays(today, 30), zone).filter(item => item.kind === 'event' && item.date > today &&
    ['exam', 'assignment', 'class'].includes(item.category))
  const existing = expand(workspace.records, addDays(today, -1), addDays(today, 1), zone)
  const slots = freeSlots(existing, today, prefs, now)
  const minutes = slotMinutes(slots)
  const duration = minutes >= 60 ? `${Math.floor(minutes / 60)}h ${minutes % 60 ? `${minutes % 60}m` : ''}` : `${minutes}m`
  const welcome = prefs.name === 'Student' ? 'Your day, at a glance.' : `Your day, ${prefs.name.split(' ')[0]}.`

  return <div className="today-view">
    <header className="page-heading today-heading">
      <div><p className="day-label"><CalendarDays size={15} />{dateLabel(today, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}</p><h1>{welcome}</h1>
        <p>See your classes, deadlines, and open time in one place.</p></div>
      <button className="button secondary" onClick={() => { setDay(today); nav('calendar') }}><CalendarDays size={16} /> Open calendar <ArrowRight size={15} className="button-arrow" /></button>
    </header>
    {!workspace.records.length && canEdit && <div className="onboard">
      <div className="onboard-icon"><Compass size={21} /></div><div><strong>Set up your first day</strong><p>Add a class or a deadline, import a calendar, or explore with example data.</p></div>
      <div className="inline"><button className="button secondary" onClick={sample}>Load sample data</button><button className="button primary" onClick={() => create('event')}><Plus size={16} /> Add event</button></div>
    </div>}
    <div className="metrics">
      <Metric icon={CalendarDays} tint="teal" value={events.length} label="Events today" />
      <Metric icon={ClipboardList} tint="violet" value={due.filter(item => item.due === today).length} label="Tasks due today" />
      <Metric icon={Clock3} tint="amber" value={duration.trim()} label="Free time left today" />
    </div>
    <div className="today-columns">
      <section className="panel schedule-panel">
        <SectionTitle title="Today’s schedule" action="View calendar" onAction={() => { setDay(today); nav('calendar') }} />
        <div className="week-strip">{week.map(day => <button key={day} aria-label={dateLabel(day, { weekday: 'long', month: 'long', day: 'numeric' })} aria-current={day === today ? 'date' : undefined}
          onClick={() => { setDay(day); nav('calendar', 'day') }} className={day === today ? 'current' : ''}>
          <span>{dateLabel(day, { weekday: 'short' })}</span><strong>{Number(day.slice(-2))}</strong>
          <i className={weekItems.some(item => item.kind === 'event' && includesDay(item, day)) ? 'marked' : ''} />
        </button>)}</div>
        <div className="schedule-list">
          {events.length ? events.map(item => <EventRow key={item.key} item={item} zone={zone} onClick={() => open(item)} />)
            : <Empty title="Your schedule is clear" detail="Classes, exams, and study blocks for today will appear here."
              action={canEdit && <button className="text-button" onClick={() => create('event')}><Plus size={16} /> Add event</button>} />}
        </div>
      </section>
      <div className="today-side">
        <section className="panel tasks-panel">
          <SectionTitle title="Next tasks" action="All tasks" onAction={() => nav('tasks')} />
          <div className="task-list">{[...due, ...undated].slice(0, 4).map(item => <TaskRow key={item.key || item.id} item={item} today={today}
            onOpen={() => open(item)} onToggle={canEdit && item.source === 'manual' ? () => toggle(item) : null} compact />)}
            {!due.length && !undated.length && <Empty icon={ClipboardList} title="No upcoming tasks" action={canEdit && <button className="text-button" onClick={() => create('task')}><Plus size={16} /> Add task</button>} />}</div>
        </section>
        <section className="plan-prompt">
          <div className="plan-icon"><BookOpen size={20} /></div>
          <div><h2>Make time to study</h2><p>{slots.length ? `Next free slot at ${timeLabel(slots[0].start, zone)}.` : 'Find free time around your timetable.'}</p></div>
          <button className="plan-link" onClick={() => nav('study')}>Plan today <ArrowRight size={16} /></button>
        </section>
      </div>
    </div>
    {!!upcoming.length && <section className="panel upcoming-panel">
      <SectionTitle title="Coming up" action="Browse calendar" onAction={() => nav('calendar')} />
      <div className="upcoming-grid">{upcoming.slice(0, 3).map(item => <button key={item.key} onClick={() => open(item)} className="upcoming-item">
        <span className={`metric-icon ${item.color}`}>{item.category === 'exam' ? <CircleAlert size={18} /> : <LayoutGrid size={18} />}</span>
        <span><strong>{item.title}</strong><small>{dateLabel(item.date)} · {categories[item.category]}</small></span></button>)}</div>
    </section>}
  </div>
}
