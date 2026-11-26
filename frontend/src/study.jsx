import { useMemo, useState } from 'react'
import { AlertTriangle, BookOpen, CalendarCheck, CalendarDays, Clock3, GraduationCap, ListChecks, Plus, Trash2 } from 'lucide-react'
import { addDays, attendanceSummary, buildPlan, conflicts, dateLabel, dayDistance, expand, freeSlots, includesDay, slotMinutes, taskOrder, timeLabel } from './planner.js'
import { AttendanceProjection, Empty, ErrorText, EventRow, Field, IconButton, Modal, SectionTitle, Tag, TaskRow } from './ui.jsx'

const tabs = { time: 'Study time', subjects: 'Subjects', attendance: 'Attendance', exams: 'Exam prep' }

function minutesLabel(value) {
  return value > 59 ? `${Math.floor(value / 60)}h${value % 60 ? ` ${value % 60}m` : ''}` : `${value}m`
}

function PlanPreview({ preview, zone, onClose, onConfirm }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  return <Modal title="Review your study plan" onClose={onClose}>
    <div className="form-body">
      {preview.blocks.length > 0 ? <><p className="muted small">{preview.blocks.length} study blocks will be added to your calendar.</p>
        <div className="preview-list">{preview.blocks.map(block => <EventRow key={block.start} item={block} zone={zone} withDate />)}</div></>
        : <p>No selected work fits in the available time.</p>}
      {!!preview.unfinished.length && <div className="warning-panel"><AlertTriangle size={18} /><div><strong>Work left to schedule</strong>
        {preview.unfinished.map((item, i) => <p key={i}>{item.title} · {minutesLabel(item.minutes)}</p>)}</div></div>}
      <ErrorText error={error} />
    </div>
    <div className="dialog-actions"><button className="button secondary" onClick={onClose}>Back</button>
      <button className="button primary" disabled={busy || !preview.blocks.length} onClick={async () => {
        setBusy(true)
        setError('')
        try { await onConfirm(preview); onClose() } catch (reason) { setError(reason.message) } finally { setBusy(false) }
      }}>{busy ? 'Adding…' : 'Confirm and add'}</button></div>
  </Modal>
}

function StudyTime({ workspace, today, now, matches, open, confirm, canEdit }) {
  const [day, setDay] = useState(today)
  const [selection, setSelection] = useState([])
  const [preview, setPreview] = useState(null)
  const prefs = workspace.preferences
  const zone = prefs.timezone
  const weekEnd = addDays(day, 6)
  const items = useMemo(() => expand(workspace.records, addDays(day, -1), addDays(weekEnd, 1), zone), [workspace.records, day, weekEnd, zone])
  const slots = freeSlots(items, day, prefs, now)
  const count = slotMinutes(slots)
  const dates = Array.from({ length: 7 }, (_, index) => addDays(day, index))
  const weekMinutes = dates.reduce((sum, date) => sum + slotMinutes(freeSlots(items, date, prefs, now)), 0)
  const plain = workspace.records.filter(item => item.kind === 'task' && item.repeat === 'none' && !item.done).map(item => ({ ...item, key: item.id }))
  const repeating = items.filter(item => item.kind === 'task' && item.repeat !== 'none' && !item.done && item.date >= day)
  const plannerTasks = taskOrder([...plain, ...repeating].filter(item => item.kind === 'task'))
  const candidates = plannerTasks.filter(item => !item.due || item.due <= weekEnd).sort((a, b) => {
    const lateA = Boolean(a.due && a.due < day), lateB = Boolean(b.due && b.due < day)
    return Number(lateA) - Number(lateB)
  })
  const workDue = candidates.filter(item => item.due && item.due >= day)
  const workMinutes = workDue.reduce((total, item) => total + item.minutes, 0)
  const earliestSlot = slots[0] ? Math.floor((slots[0].end - slots[0].start) / 60000) : 0
  const fits = candidates.filter(item => item.minutes <= earliestSlot && (!item.due || item.due >= day)).slice(0, 3)
  const clashes = conflicts(items.filter(item => includesDay(item, day)), zone, prefs.buffer, matches.copies)
  const selected = candidates.filter(item => selection.includes(item.key))

  return <>
    <div className="study-grid">
      <section className="panel inset"><SectionTitle title="Free slots" /><Field label="Planning date"><input type="date" value={day} min={today} max={addDays(today, 365)} onChange={e => e.target.value && setDay(e.target.value)} /></Field>
        <div className="space-top">{slots.length ? <div className="slot-list">{slots.slice(0, 8).map(slot => <div key={slot.start}><Clock3 size={16} /><strong>{timeLabel(slot.start, zone)}–{timeLabel(slot.end, zone)}</strong><Tag color="teal">{minutesLabel(Math.floor((slot.end - slot.start) / 60000))}</Tag></div>)}</div>
          : <Empty icon={Clock3} title="No free time on this date" detail="Adjust planning hours in Settings or select another day." />}</div>
      </section>
      <section className="panel inset"><SectionTitle title="Workload · next 7 days" />
        <div className="workload"><div><strong>{minutesLabel(workMinutes)}</strong><span>Estimated work due</span></div><div><strong>{minutesLabel(weekMinutes)}</strong><span>Free study time</span></div></div>
        <progress aria-label="Weekly workload" value={Math.min(weekMinutes || 1, workMinutes)} max={weekMinutes || 1} />
        <p className="muted small">{workMinutes > weekMinutes ? 'Estimated work exceeds your free time.' : 'Free time accounts for busy events and your time buffer.'}</p>
        <h3>Fits your next gap</h3>
        {fits.length ? <div className="line-list">{fits.map(item => <button key={item.key} onClick={() => open(item)}><strong>{item.title}</strong><span>{item.minutes} min</span></button>)}</div>
          : <p className="muted small">No estimated tasks fit the next gap.</p>}
      </section>
    </div>
    <div className="study-grid">
      <section className="panel inset"><SectionTitle title="Make a study plan" /><p className="muted small">Choose tasks to timebox on {dateLabel(day)}. Daymark suggests blocks of up to 45 minutes with short breaks.</p>
        {candidates.length ? <div className="study-options">{candidates.slice(0, 45).map(item => <label className="study-option" key={item.key}>
          <input type="checkbox" checked={selection.includes(item.key)} disabled={!canEdit} onChange={() => setSelection(current => current.includes(item.key) ? current.filter(key => key !== item.key) : [...current, item.key])} />
          <span><strong>{item.title}</strong><small>{item.due ? `Due ${dateLabel(item.due)}` : 'No due date'}</small></span><span>{item.minutes}m</span>
        </label>)}</div> : <Empty icon={ListChecks} title="No open work to plan" />}
        <button className="button primary space-top" disabled={!selected.length || !canEdit} onClick={() => setPreview({
          ...buildPlan(selected.map(item => ({ ...item, id: item.repeat === 'none' ? item.id : item.key })), items, day, day, prefs, now), revision: workspace.revision,
        })}>Preview study plan</button>
      </section>
      <section className="panel inset"><SectionTitle title="Timetable checks" /><p className="muted small">Overlaps and room changes shorter than your {prefs.buffer}-minute buffer.</p>
      {clashes.length ? <div className="conflict-list">{clashes.map(({ first, second, minutes }) => <div key={first.key + second.key}>
        <AlertTriangle size={18} /><div><strong>{minutes < 0 ? 'Overlapping events' : `Only ${minutes} min between rooms`}</strong>
          <p><button onClick={() => open(first)}>{first.title}</button> · <button onClick={() => open(second)}>{second.title}</button></p></div></div>)}</div>
        : <Empty icon={CalendarCheck} title="No conflicts found" />}</section>
    </div>
    {preview && <PlanPreview preview={preview} zone={zone} onClose={() => setPreview(null)} onConfirm={confirm} />}
  </>
}

function Subjects({ workspace, courses, today, open, create, canEdit }) {
  const [active, setActive] = useState('')
  const [past, setPast] = useState(false)
  const current = courses.find(item => item.course === active) || courses[0]
  const records = workspace.records.filter(item => item.kind !== 'course' && item.kind !== 'attendance' && item.course && item.course.toLowerCase() === current?.course.toLowerCase())
  const zone = workspace.preferences.timezone
  const upcoming = expand(records, addDays(today, past ? -60 : 0), addDays(today, 90), zone).slice(0, 18)
  return <section className="panel inset">
    <SectionTitle title="Your subjects" />
    {!courses.length ? <Empty icon={BookOpen} title="No subjects yet" detail="Add a subject code to tie together classes, exams, and tasks."
      action={canEdit && <button className="button primary" onClick={() => create('course')}><Plus size={16} /> Add subject</button>} />
      : <><div className="subject-picker"><Field label="Subject"><select value={current.course} onChange={e => setActive(e.target.value)}>
        {courses.map(item => <option key={item.id} value={item.course}>{item.title} · {item.course}</option>)}</select></Field>
        {canEdit && <button className="button secondary" onClick={() => create('course')}><Plus size={16} /> New subject</button>}</div>
      <div className="subject-detail"><Tag color={current.color}>{current.course}</Tag><h3>{current.title}</h3>
        {current.notes && <p className="notes">{current.notes}</p>}
        {canEdit && <div className="inline wrap">
          <button className="button secondary" onClick={() => current.source ? open(current) :
            create('course', { course: current.course, title: current.title })}>{current.source ? 'Subject details' : 'Save subject and notes'}</button>
          <button className="button secondary" onClick={() => create('task', { course: current.course })}>Add task</button>
          <button className="button secondary" onClick={() => create('event', { course: current.course, category: 'class' })}>Add class</button>
        </div>}</div>
      <label className="check-label"><input type="checkbox" checked={past} onChange={e => setPast(e.target.checked)} /> Include past items</label>
      <div className="space-top">{upcoming.length ? upcoming.map(item => item.kind === 'event'
        ? <EventRow key={item.key} item={item} zone={zone} withDate onClick={() => open(item)} />
        : <TaskRow key={item.key} item={item} today={today} onOpen={() => open(item)} />)
        : <Empty title="No dated items for this subject" />}</div></>}
  </section>
}

function Attendance({ workspace, courses, open, create, canEdit }) {
  const [subject, setSubject] = useState('')
  const course = courses.find(item => item.course === subject) || courses[0]
  const counts = course && attendanceSummary(workspace.records, course)
  const logs = workspace.records.filter(item => item.kind === 'attendance' && item.course.toLowerCase() === course?.course.toLowerCase())
    .sort((a, b) => b.due.localeCompare(a.due))
  return <div className="study-grid"><section className="panel inset">
    <SectionTitle title="Attendance tracker" /><p className="small muted">Attendance comes from your recorded check-ins. Excused classes are excluded from the percentage.</p>
    {course ? <><Field label="Subject"><select value={course.course} onChange={e => setSubject(e.target.value)}>
      {courses.map(item => <option value={item.course} key={item.id}>{item.title}</option>)}</select></Field>
      <div className="attendance-rate"><strong>{counts.percent === null ? '—' : `${counts.percent}%`}</strong><Tag color={counts.percent !== null && counts.percent < course.target ? 'rose' : 'teal'}>Target {course.target}%</Tag></div>
      <p className="muted small">{counts.present} present · {counts.absent} absent · {counts.excused} excused</p>
      <AttendanceProjection key={course.id} counts={counts} target={course.target} /></>
      : <Empty icon={GraduationCap} title="Add a subject first" action={canEdit && <button className="button primary" onClick={() => create('course')}>Add subject</button>} />}
    </section><section className="panel inset"><SectionTitle title="Check-ins" />
      {course && canEdit && <button className="button primary" onClick={() => create('attendance', { course: course.course, title: course.title })}><Plus size={16} /> Log attendance</button>}
      {logs.length ? <div className="line-list space-top">{logs.map(item => <button key={item.id} onClick={() => open(item)}>
        <strong>{dateLabel(item.due)}</strong><Tag color={item.attendance === 'absent' ? 'rose' : item.attendance === 'excused' ? 'amber' : 'teal'}>{item.attendance}</Tag>
      </button>)}</div> : <Empty icon={CalendarCheck} title="No check-ins recorded" />}</section></div>
}

function ExamPrep({ workspace, today, now, confirm, canEdit }) {
  const [date, setDate] = useState(addDays(today, 7))
  const [examId, setExamId] = useState('')
  const [topics, setTopics] = useState([{ id: 0, title: '', minutes: 60 }])
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState('')
  const prefs = workspace.preferences
  const exams = expand(workspace.records, today, addDays(today, 90), prefs.timezone).filter(item => item.kind === 'event' && item.category === 'exam')
  function previewExam(event) {
    event.preventDefault()
    setError('')
    const distance = dayDistance(today, date)
    if (!Number.isFinite(distance) || distance < 1 || distance > 90) return setError('Choose an exam 1–90 days away.')
    const until = addDays(date, -1)
    const exam = exams.find(item => item.key === examId)
    const records = expand(workspace.records, addDays(today, -1), date, prefs.timezone)
    const tasks = topics.map(topic => ({ ...topic, id: undefined, title: topic.title.trim(), due: until, priority: 'normal', course: exam?.course || '' }))
    if (tasks.some(topic => !topic.title)) return setError('Enter a name for each topic.')
    setPreview({ ...buildPlan(tasks, records, today, until, prefs, now, true), revision: workspace.revision })
  }
  return <section className="panel inset exam-panel"><SectionTitle title="Create a revision plan" />
    <p className="small muted">List the topics you need to cover. Daymark spreads revision across open slots before the exam.</p>
    <form onSubmit={previewExam} className="stack">
      <div className="form-grid">
        <Field label="Calendar exam"><select value={examId} onChange={e => {
          setExamId(e.target.value)
          const item = exams.find(exam => exam.key === e.target.value)
          if (item) setDate(item.date)
        }}><option value="">Choose a date manually</option>{exams.map(exam => <option value={exam.key} key={exam.key}>{exam.title} · {dateLabel(exam.date)}</option>)}</select></Field>
        <Field label="Exam date"><input type="date" required min={addDays(today, 1)} max={addDays(today, 90)} value={date} onChange={e => { setDate(e.target.value); setExamId('') }} /></Field>
      </div>
      {topics.map((topic, index) => <div className="topic" key={topic.id}>
        <Field label={`Topic ${index + 1}`}><input required maxLength={200} placeholder="e.g. Relational algebra" value={topic.title} onChange={e => setTopics(current => current.map(item => item.id === topic.id ? { ...item, title: e.target.value } : item))} /></Field>
        <Field label="Minutes"><input type="number" min="15" max="480" value={topic.minutes} required onChange={e => setTopics(current => current.map(item => item.id === topic.id ? { ...item, minutes: Number(e.target.value) } : item))} /></Field>
        <IconButton icon={Trash2} label={`Remove topic ${index + 1}`} disabled={topics.length === 1} onClick={() => setTopics(current => current.filter(item => item.id !== topic.id))} /></div>)}
      <ErrorText error={error} />
      <div className="inline wrap"><button className="button secondary" type="button" disabled={topics.length >= 25} onClick={() => setTopics(current => [...current, { id: Math.max(...current.map(item => item.id)) + 1, title: '', minutes: 60 }])}><Plus size={16} /> Add topic</button>
        <button className="button primary" disabled={!canEdit}>Preview revision plan</button></div>
    </form>
    {preview && <PlanPreview preview={preview} zone={prefs.timezone} onClose={() => setPreview(null)} onConfirm={confirm} />}
  </section>
}

export function Study(props) {
  const [tab, setTab] = useState('time')
  return <><header className="page-heading"><div><h1>Study</h1><p>Fit focused work around classes and stay ahead of exams.</p></div></header>
    <div className="tabs" aria-label="Study tools">{Object.entries(tabs).map(([value, label]) => <button key={value} aria-pressed={value === tab}
      className={value === tab ? 'active' : ''} onClick={() => setTab(value)}>{label}</button>)}</div>
    {tab === 'time' && <StudyTime {...props} />}
    {tab === 'subjects' && <Subjects {...props} />}
    {tab === 'attendance' && <Attendance {...props} />}
    {tab === 'exams' && <ExamPrep {...props} />}
  </>
}
