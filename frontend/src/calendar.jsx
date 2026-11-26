import { useMemo, useState } from 'react'
import { CalendarDays, ChevronLeft, ChevronRight, Plus, SlidersHorizontal } from 'lucide-react'
import { addDays, categories, dateLabel, expand, includesDay, instant, monthShift, sources, timeLabel, wall, weekStart } from './planner.js'
import { Empty, IconButton, Tag } from './ui.jsx'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const modes = ['month', 'week', 'day']

function calendarTitle(day, mode) {
  if (mode === 'month') return dateLabel(day, { month: 'long', year: 'numeric' })
  if (mode === 'day') return dateLabel(day, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
  return `${dateLabel(weekStart(day))} – ${dateLabel(addDays(weekStart(day), 6))}, ${day.slice(0, 4)}`
}

function itemsOn(items, day) {
  return items.filter(item => includesDay(item, day))
}
function stateClass(date, today, active) {
  return date === today ? 'is-today' : date === active ? 'is-selected' : ''
}

function Month({ focus, today, items, open, pick, zone }) {
  const first = weekStart(focus.slice(0, 7) + '-01')
  return <div className="month-scroll"><div className="month-grid">
    {DAYS.map(day => <div key={day} className="weekday">{day}</div>)}
    {Array.from({ length: 42 }, (_, i) => {
      const day = addDays(first, i)
      const events = itemsOn(items, day)
      return <div key={day} className={`month-cell ${stateClass(day, today, focus)} ${day.slice(0, 7) !== focus.slice(0, 7) ? 'outside' : ''}`}>
        <button className="date-cell" aria-label={`Open ${dateLabel(day, { weekday: 'long', month: 'long', day: 'numeric' })}`} onClick={() => pick(day)}>
          {Number(day.slice(-2))}
        </button>
        {events.slice(0, 3).map(item => <button className={`month-item ${item.color} ${item.done ? 'crossed' : ''}`} key={item.key} onClick={() => open(item)}>
          <i />{item.kind === 'event' && !item.allDay && item.date === day && <span>{timeLabel(item.start, zone)}</span>}<strong>{item.title}</strong>
        </button>)}
        {events.length > 3 && <button className="more" onClick={() => pick(day)}>+{events.length - 3} more</button>}
      </div>
    })}
  </div></div>
}

function position(item, day, zone) {
  const startDay = wall(item.start, zone)
  const endDay = wall(item.end, zone)
  function minutes(value) { return Number(value.slice(11, 13)) * 60 + Number(value.slice(14, 16)) }
  return { item, start: startDay.slice(0, 10) < day ? 0 : minutes(startDay),
    end: endDay.slice(0, 10) > day ? 1440 : minutes(endDay) }
}

function lanes(events) {
  let active = [], group = [], max = 1
  const positioned = []
  for (const event of events) {
    active = active.filter(item => item.end > event.start)
    if (!active.length) {
      positioned.push(...group.map(item => ({ ...item, total: max })))
      group = []
      max = 1
    }
    let lane = 0
    while (active.some(item => item.lane === lane)) lane++
    const item = { ...event, lane }
    active.push(item)
    group.push(item)
    max = Math.max(max, lane + 1)
  }
  return [...positioned, ...group.map(item => ({ ...item, total: max }))]
}

function Timeline({ mode, focus, today, items, open, pick, prefs, now, create, canEdit }) {
  const zone = prefs.timezone
  const days = mode === 'day' ? [focus] : Array.from({ length: 7 }, (_, index) => addDays(weekStart(focus), index))
  const positions = days.map(day => itemsOn(items, day).filter(item => item.kind === 'event' && !item.allDay)
    .map(item => position(item, day, zone)).sort((a, b) => a.start - b.start || a.end - b.end))
  const all = positions.flat()
  const first = Math.min(prefs.day_start, ...all.map(item => Math.floor(item.start / 60)))
  const last = Math.max(prefs.day_end, ...all.map(item => Math.ceil(item.end / 60)))
  const total = (last - first) * 60
  const labels = Array.from({ length: last - first }, (_, index) => String(first + index).padStart(2, '0') + ':00')
  const nowWall = wall(now, zone)
  const nowMinutes = Number(nowWall.slice(11, 13)) * 60 + Number(nowWall.slice(14, 16))
  return <div className="timeline-overflow"><div className={`time-grid ${mode}`} style={{ '--days': days.length, '--height': `${(last - first) * 58}px`, '--hour': '58px' }}>
    <div className="time-grid-zone" title={zone}>Time</div>
    {days.map(day => <button className={`timeline-day ${stateClass(day, today, focus)}`} key={day} onClick={() => pick(day)}>
      <span>{dateLabel(day, { weekday: 'short' })}</span><strong>{Number(day.slice(-2))}</strong>
    </button>)}
    <div className="all-day-label">All day</div>
    {days.map(day => <div className="timeline-all-day" key={day}>
      {itemsOn(items, day).filter(item => item.allDay || item.kind === 'task').map(item =>
        <button key={item.key} className={`month-item ${item.color} ${item.done ? 'crossed' : ''}`} onClick={() => open(item)}><i /><strong>{item.title}</strong></button>)}
    </div>)}
    <div className="timeline-labels">{labels.map(label => <span key={label}>{label}</span>)}</div>
    {days.map((day, index) => <div className="time-track" key={day}>
      {canEdit && labels.map((label, i) => <button key={label} className="time-slot" aria-label={`Add event on ${dateLabel(day)} at ${label}`} style={{ top: `${i * 58}px` }}
        onClick={() => {
          const start = instant(day + 'T' + label, zone)
          create('event', { start: new Date(start).toISOString(), end: new Date(start + 3600000).toISOString() })
        }} />)}
      {lanes(positions[index]).map(({ item, start, end, lane, total: count }) => <button key={item.key} onClick={() => open(item)}
        className={`timed-item ${item.color}`}
        style={{ top: `${(start - first * 60) / total * 100}%`, height: `max(24px, ${(end - start) / total * 100}%)`,
          left: `calc(${lane / count * 100}% + 4px)`, width: `calc(${100 / count}% - 8px)` }}>
        <strong>{item.title}</strong><small>{timeLabel(item.start, zone)}–{timeLabel(item.end, zone)}{item.location && ` · ${item.location}`}</small>
      </button>)}
      {day === today && nowMinutes >= first * 60 && nowMinutes < last * 60 && <div className="now-line" style={{ top: `${(nowMinutes - first * 60) / total * 100}%` }} />}
    </div>)}
  </div></div>
}

export function CalendarView({ day, setDay, mode, setMode, records, prefs, today, now, open, create, canEdit, hidden, setHidden }) {
  const [filters, setFilters] = useState(false)
  const first = mode === 'month' ? weekStart(day.slice(0, 7) + '-01') : mode === 'week' ? weekStart(day) : day
  const last = addDays(first, mode === 'month' ? 41 : mode === 'week' ? 6 : 0)
  const availableSources = useMemo(() => [...new Set(records.map(item => item.source))], [records])
  const items = useMemo(() => expand(records.filter(item => !hidden.includes(item.source) &&
    !hidden.includes(item.kind === 'task' ? 'task' : item.category)), first, last, prefs.timezone), [records, first, last, prefs.timezone, hidden])
  function move(delta) { setDay(mode === 'month' ? monthShift(day, delta) : addDays(day, delta * (mode === 'week' ? 7 : 1))) }
  function pick(target) { setDay(target); setMode('day') }
  function flip(id) { setHidden(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id]) }
  return <>
    <header className="page-heading"><div><h1>Calendar</h1><p>Classes, deadlines, and study blocks share one timetable.</p></div>
      {canEdit && <button className="button primary" onClick={() => create('event')}><Plus size={17} /> New event</button>}</header>
    <section className="panel calendar-panel">
      <div className="calendar-toolbar">
        <div className="calendar-navigation"><div className="inline"><IconButton icon={ChevronLeft} label="Previous period" onClick={() => move(-1)} />
          <IconButton icon={ChevronRight} label="Next period" onClick={() => move(1)} /></div>
          <h2>{calendarTitle(day, mode)}</h2></div>
        <div className="calendar-actions"><button className="button secondary" onClick={() => setDay(today)}>Today</button>
          <div className="segment" aria-label="Calendar view">{modes.map(view => <button key={view} aria-pressed={mode === view} className={mode === view ? 'active' : ''} onClick={() => setMode(view)}>{view}</button>)}</div>
          <button className="button secondary" aria-expanded={filters} onClick={() => setFilters(value => !value)}><SlidersHorizontal size={16} /> <span>Filters{hidden.length ? ` (${hidden.length})` : ''}</span></button></div>
      </div>
      {filters && <div className="calendar-filters"><div><strong>Types</strong><div className="filter-options">{Object.entries({ ...categories, task: 'Task' }).map(([id, label]) =>
        <label className="check-label" key={id}><input type="checkbox" checked={!hidden.includes(id)} onChange={() => flip(id)} />{label}</label>)}</div></div>
        {!!availableSources.length && <div><strong>Sources</strong><div className="filter-options">{availableSources.map(id => <label className="check-label" key={id}><input type="checkbox" checked={!hidden.includes(id)} onChange={() => flip(id)} />{sources[id]}</label>)}</div></div>}</div>}
      {mode === 'month' ? <Month focus={day} today={today} items={items} open={open} pick={pick} zone={prefs.timezone} />
        : <Timeline mode={mode} focus={day} today={today} items={items} open={open} pick={pick} prefs={prefs} now={now} create={create} canEdit={canEdit} />}
    </section>
    {mode === 'day' && <section className="panel day-list">
      <h2>Day agenda</h2>
      {items.length ? <div className="line-list">{items.map(item => <button key={item.key} onClick={() => open(item)}>
        <Tag color={item.color}>{item.kind === 'event' ? categories[item.category] : 'Task'}</Tag><strong>{item.title}</strong>
        <span>{item.kind === 'event' && !item.allDay ? timeLabel(item.start, prefs.timezone) : 'All day'}</span>
      </button>)}</div> : <Empty icon={CalendarDays} title="No items for this day" />}
    </section>}
  </>
}
