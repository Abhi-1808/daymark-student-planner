import { Children, cloneElement, useEffect, useId, useRef, useState } from 'react'
import { AlertCircle, CalendarDays, Check, ChevronRight, Clock3, Flag, MapPin, X } from 'lucide-react'
import { categories, dateLabel, dayOf, sources, timeLabel } from './planner.js'

export function IconButton({ icon: Icon, label, className = '', ...props }) {
  return <button type="button" className={`icon-button ${className}`} aria-label={label} title={label} {...props}><Icon size={17} /></button>
}
export function SectionTitle({ title, action, onAction }) {
  return <header className="section-heading"><h2>{title}</h2>{action && <button className="text-button" onClick={onAction}>{action}<ChevronRight size={15} /></button>}</header>
}
export function Empty({ icon: Icon = CalendarDays, title, detail, action }) {
  return <div className="empty"><span className="empty-icon"><Icon size={22} /></span><strong>{title}</strong>{detail && <p>{detail}</p>}{action}</div>
}
export function ErrorText({ error }) {
  return error && <p className="error-msg" role="alert"><AlertCircle size={16} />{error}</p>
}
export function Modal({ title, children, onClose, className = '' }) {
  const dialog = useRef(null)
  useEffect(() => {
    const element = dialog.current
    const opener = document.activeElement
    element.showModal()
    return () => {
      element.close()
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus()
    }
  }, [])
  return <dialog ref={dialog} className={`dialog ${className}`}
    onCancel={event => { event.preventDefault(); onClose() }}
    onClick={event => { if (event.target === dialog.current) onClose() }}>
    <div className="dialog-inner"><header className="dialog-head"><h2>{title}</h2><IconButton icon={X} label="Close dialog" onClick={onClose} /></header>{children}</div>
  </dialog>
}
export function Field({ label, children, className = '' }) {
  const id = useId()
  const [control, ...extra] = Children.toArray(children)
  return <div className={`field ${className}`}><label htmlFor={id}>{label}</label>{cloneElement(control, { id })}{extra}</div>
}
export function Tag({ children, color = 'teal' }) {
  return <span className={`tag ${color}`}>{children}</span>
}

export function EventRow({ item, zone, onClick, withDate = false }) {
  const when = item.allDay || item.start?.length === 10 ? 'All day' : item.start ? timeLabel(item.start, zone) : ''
  const classification = item.course || categories[item.category]
  const Element = onClick ? "button" : "div"
  return <Element className="event-row" onClick={onClick}>
    <span className="event-time">{withDate && <strong>{dateLabel(dayOf(item.start, zone))}</strong>}{when}</span>
    <span className={`event-line ${item.color}`} />
    <span className="event-description"><strong>{item.title}</strong><span>{classification}{item.location && <><span className="dot-separator" /><MapPin size={12} />{item.location}</>}</span></span>
    {onClick && <ChevronRight className="row-chevron" size={16} />}
  </Element>
}
export function TaskRow({ item, onOpen, onToggle, today, compact = false }) {
  const outstanding = !item.done
  const late = outstanding && item.due && item.due < today
  return <div className={`task-row ${item.done ? 'completed' : ''} ${compact ? 'compact' : ''}`}>
    <button className="check-button" aria-label={`${item.done ? 'Reopen' : 'Complete'} ${item.title}`}
      aria-pressed={item.done} onClick={onToggle} disabled={!onToggle}>{item.done && <Check size={13} />}</button>
    <button className="task-description" onClick={onOpen}>
      <strong>{item.title}</strong>
      <span>{item.course && <>{item.course}<span className="dot-separator" /></>}
        {item.due ? <span className={late ? 'late' : ''}>{item.due === today ? 'Due today' : `Due ${dateLabel(item.due)}`}</span> : 'No due date'}
        {!compact && <><span className="dot-separator" /><Clock3 size={12} />{item.minutes} min</>}
      </span>
    </button>
    {outstanding && item.priority === 'high' && <Tag color="rose"><Flag size={11} /> High</Tag>}
    {!compact && item.source !== 'manual' && <span className="small muted">{sources[item.source]}</span>}
  </div>
}

export function AttendanceProjection({ counts, target }) {
  const [future, setFuture] = useState('1')
  const [miss, setMiss] = useState('0')
  const classes = Number(future)
  const misses = Math.min(Number(miss), classes)
  const denominator = counts.total + classes
  const projected = denominator ? Math.round((counts.present + classes - misses) / denominator * 1000) / 10 : null
  const needed = target === 100 ? (counts.absent ? Infinity : 0)
    : Math.max(0, Math.ceil((target * counts.total - 100 * counts.present) / (100 - target)))
  return <details className="projection"><summary>Attendance projection</summary>
    <div className="form-grid"><Field label="Upcoming classes"><input type="number" min="0" max="1000" value={future} onChange={e => setFuture(String(Math.max(0, Math.min(1000, Number(e.target.value)))))} /></Field>
      <Field label="Classes missed"><input type="number" min="0" max={classes} value={misses} onChange={e => setMiss(String(Math.max(0, Math.min(classes, Number(e.target.value)))))} /></Field></div>
    <p>Projected attendance <strong>{projected === null ? '—' : `${projected}%`}</strong></p>
    {needed > 0 && <p>{Number.isFinite(needed) ? `Attend the next ${needed} in a row to reach ${target}%.` : 'A 100% target is unreachable with recorded absences.'}</p>}
  </details>
}
