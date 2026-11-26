import { useState } from 'react'
import { CalendarDays, FileText, MapPin, Trash2 } from 'lucide-react'
import { addDays, categories, colors, dateLabel, dayOf, defaults, inputRecord, instant, sources, timeLabel, wall } from './planner.js'
import { ErrorText, Field, Modal, Tag } from './ui.jsx'

export function makeDraft(kind, day, timezone, options = {}) {
  const start = instant(day + 'T09:00', timezone)
  return { ...defaults, kind,
    ...(kind === 'event' ? { start: new Date(start).toISOString(), end: new Date(start + 3600000).toISOString() } : {}),
    ...(kind === 'task' || kind === 'attendance' ? { due: day } : {}),
    ...options,
  }
}

function fieldsFor(record, timezone) {
  const allDay = record.start?.length === 10
  return {
    ...inputRecord(record), allDay: Boolean(allDay),
    start: !record.start || allDay ? record.start || '' : wall(record.start, timezone),
    end: !record.end ? '' : allDay ? addDays(record.end, -1) : wall(record.end, timezone),
    due: record.due || '', repeat_until: record.repeat_until || '',
  }
}

export function RecordEditor({ record, courses, zone, close, save, remove, skip, canEdit, checkWarnings }) {
  const [mode, setMode] = useState(record.id ? 'view' : 'edit')
  const [data, setData] = useState(() => fieldsFor(record, zone))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const [warnings, setWarnings] = useState([])
  const label = { event: 'Event', task: 'Task', course: 'Subject', attendance: 'Attendance' }[data.kind]
  const editable = canEdit && (!record.id || record.source === 'manual')
  const update = (key, value) => {
    setWarnings([])
    setData(current => ({ ...current, [key]: value }))
  }
  const prop = key => ({ value: data[key], onChange: event => update(key, event.target.value) })
  const title = mode === 'view' ? `${label} details` : record.id ? `Edit ${label.toLowerCase()}` : `New ${label.toLowerCase()}`

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const body = inputRecord(data)
      body.due = data.due || null
      body.repeat_until = data.repeat === 'none' ? null : data.repeat_until || null
      if (data.kind === 'event') {
        body.start = data.allDay ? data.start : new Date(instant(data.start, zone)).toISOString()
        body.end = data.allDay ? addDays(data.end, 1) : new Date(instant(data.end, zone)).toISOString()
      }
      if (body.repeat_until && body.repeat_until < (body.kind === 'event' ? data.start.slice(0, 10) : body.due || '')) {
        throw new Error('The repeat end date must be on or after the first occurrence.')
      }
      if (body.kind === 'task' && !body.due && body.reminder !== null) throw new Error('Set a due date for the reminder.')
      if (data.kind === 'course' && !body.course) throw new Error('Enter a subject code.')
      const id = mode === 'copy' ? undefined : record.id
      if (!warnings.length) {
        const clashes = checkWarnings(body, id)
        if (clashes.length) {
          setWarnings(clashes)
          return
        }
      }
      await save(body, id)
      close()
    } catch (cause) {
      setError(cause.message)
    } finally {
      setBusy(false)
    }
  }

  async function removeRecord(occurrence = false) {
    setBusy(true)
    try {
      await (occurrence ? skip(record) : remove(record.id))
      close()
    } catch (cause) {
      setError(cause.message)
    } finally {
      setBusy(false)
    }
  }

  function edit() {
    setData(fieldsFor(record.original || record, zone))
    setMode('edit')
  }

  if (mode === 'view') return <Modal title={title} onClose={close}>
    <div className="record-detail">
      <div className="inline"><Tag color={record.color}>{record.kind === 'event' ? categories[record.category] : label}</Tag><span className="muted small">{sources[record.source]}</span></div>
      <h3>{record.title}</h3>
      {record.kind === 'event' && <p><CalendarDays size={17} />{dateLabel(dayOf(record.start, zone), { day: 'numeric', month: 'long', weekday: 'long' })} · {record.start.length === 10 ? 'All day' : `${timeLabel(record.start, zone)}–${timeLabel(record.end, zone)}`}</p>}
      {record.due && <p><CalendarDays size={17} />{dateLabel(record.due)}</p>}
      {record.location && <p><MapPin size={17} />{record.location}</p>}
      {record.course && <p><FileText size={17} />{record.course}</p>}
      {record.kind === 'task' && <p>{record.minutes} min · {record.done ? 'Completed' : 'Open'} · {record.priority} priority</p>}
      {record.repeat !== 'none' && <p>Repeats {record.repeat}</p>}
      {record.notes && <p className="notes">{record.notes}</p>}
      {confirm && <p>Delete {record.repeat === 'none' ? 'this item' : 'the entire series'}?</p>}
      <ErrorText error={error} />
    </div>
    {editable ? <div className="dialog-actions">
      {confirm ? <><button className="button secondary" onClick={() => setConfirm(false)}>Cancel</button>
        {record.repeat !== 'none' && record.date && <button className="button secondary" disabled={busy} onClick={() => removeRecord(true)}>Skip occurrence</button>}
        <button className="button danger" disabled={busy} onClick={() => removeRecord()}>Delete {record.repeat === 'none' ? 'item' : 'series'}</button></>
        : <><button className="text-button danger-text" onClick={() => setConfirm(true)}><Trash2 size={15} /> Delete</button><button className="button primary" onClick={edit}>Edit {label.toLowerCase()}</button></>}
    </div> : canEdit && <div className="dialog-actions"><button className="button secondary" onClick={() => {
      setData(fieldsFor({ ...record, repeat: 'none' }, zone))
      setMode('copy')
    }}>Make editable copy</button></div>}
  </Modal>

  return <Modal title={mode === 'copy' ? `Copy ${label.toLowerCase()}` : title} onClose={close}>
    <form onSubmit={handleSubmit}>
      <div className="form-body">
        <Field label={data.kind === 'course' ? 'Subject name' : 'Title'}><input {...prop('title')} autoFocus required maxLength={200} placeholder={data.kind === 'course' ? 'Database Systems' : 'Name this item'} /></Field>
        {data.kind === 'event' && <>
          <div className="form-grid"><Field label="Type"><select {...prop('category')}>{Object.entries(categories).map(([key, text]) => <option value={key} key={key}>{text}</option>)}</select></Field>
            <Field label="Location"><input {...prop('location')} maxLength={200} placeholder="Optional" /></Field></div>
          <label className="check-label"><input type="checkbox" checked={data.allDay} onChange={e => {
            setWarnings([])
            const enable = e.target.checked
            setData(state => ({ ...state, allDay: enable,
              start: enable ? state.start.slice(0, 10) : state.start && state.start + 'T09:00',
              end: enable ? state.end.slice(0, 10) : state.end && state.end + 'T10:00',
            }))
          }} /> All-day event</label>
          <div className="form-grid"><Field label="Starts"><input required type={data.allDay ? 'date' : 'datetime-local'} {...prop('start')} /></Field>
            <Field label="Ends"><input required type={data.allDay ? 'date' : 'datetime-local'} {...prop('end')} /></Field></div>
          <label className="check-label"><input type="checkbox" checked={data.busy} onChange={e => update('busy', e.target.checked)} /> Block this time for study planning</label>
        </>}
        {data.kind === 'task' && <><div className="form-grid"><Field label="Due date"><input type="date" {...prop('due')} /></Field>
          <Field label="Estimate in minutes"><input type="number" required min="15" max="480" value={data.minutes} onChange={e => update('minutes', Number(e.target.value))} /></Field></div>
          <Field label="Priority"><select {...prop('priority')}><option value="normal">Normal</option><option value="high">High</option><option value="low">Low</option></select></Field></>}
        {data.kind === 'course' ? <div className="form-grid"><Field label="Subject code"><input required {...prop('course')} maxLength={80} placeholder="CSE245" /></Field>
          <Field label="Attendance target (%)"><input required type="number" min="1" max="100" value={data.target} onChange={e => update('target', Number(e.target.value))} /></Field></div>
          : <Field label="Subject"><input list="subject-codes" {...prop('course')} required={data.kind === 'attendance'} maxLength={80} placeholder="Optional subject code" /></Field>}
        <datalist id="subject-codes">{courses.map(course => <option key={course.id} value={course.course}>{course.title}</option>)}</datalist>
        {data.kind === 'attendance' && <div className="form-grid">
          <Field label="Date"><input type="date" required {...prop('due')} /></Field>
          <Field label="Status"><select {...prop('attendance')}><option value="present">Present</option><option value="absent">Absent</option><option value="excused">Excused</option></select></Field>
        </div>}
        {['event', 'task'].includes(data.kind) && mode !== 'copy' && <div className="form-grid">
          <Field label="Repeat"><select {...prop('repeat')}><option value="none">Never</option><option value="daily">Daily</option><option value="weekly">Weekly</option></select></Field>
          {data.repeat !== 'none' && <Field label="Repeat until"><input type="date" {...prop('repeat_until')} /></Field>}
        </div>}
        {['event', 'task'].includes(data.kind) && <Field label={data.kind === 'task' || data.allDay ? 'Reminder (from 09:00 on the date)' : 'Reminder (before start)'}>
          <select value={data.reminder ?? ''} onChange={event => update('reminder', event.target.value === '' ? null : Number(event.target.value))}>
            <option value="">None</option><option value="0">At the time</option><option value="10">10 minutes before</option>
            <option value="30">30 minutes before</option><option value="60">1 hour before</option><option value="1440">1 day before</option>
          </select></Field>}
        {['event', 'course'].includes(data.kind) && <Field label="Color"><select {...prop('color')}>{Object.entries(colors).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></Field>}
        <Field label={data.kind === 'course' ? 'Notes and useful links' : 'Notes'}><textarea rows="3" maxLength={10000} {...prop('notes')} placeholder="Optional" /></Field>
        {!!warnings.length && <div className="warning-panel"><div><strong>Check these timetable conflicts</strong>
          {warnings.slice(0, 7).map((warning, index) => <p key={index}>{warning.title} · {warning.minutes < 0 ? 'Overlaps' : `${warning.minutes} min between rooms`}</p>)}
        </div></div>}
        <ErrorText error={error} />
      </div>
      <div className="dialog-actions"><button type="button" className="button secondary" onClick={() => record.id ? setMode('view') : close()}>Cancel</button><button className="button primary" type="submit" disabled={busy}>{busy ? 'Saving…' : warnings.length ? 'Save anyway' : mode === 'copy' ? 'Save copy' : 'Save'}</button></div>
    </form>
  </Modal>
}
