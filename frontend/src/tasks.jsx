import { useState } from 'react'
import { ClipboardList, Plus } from 'lucide-react'
import { addDays, expand, taskOrder } from './planner.js'
import { Empty, TaskRow } from './ui.jsx'

const options = { open: 'Open', all: 'All', completed: 'Completed' }

export function Tasks({ records, today, zone, create, open, toggle, canEdit }) {
  const [filter, setFilter] = useState('open')
  const [subject, setSubject] = useState('')
  const [priority, setPriority] = useState('')
  const recurring = records.filter(item => item.kind === 'task' && item.repeat !== 'none')
  const plain = records.filter(item => item.kind === 'task' && item.repeat === 'none')
  const occurrences = expand(recurring, addDays(today, -7), addDays(today, 30), zone)
  const subjectCodes = [...new Set([...plain, ...recurring].map(item => item.course).filter(Boolean))].sort()
  const all = taskOrder([...plain, ...occurrences])
  const visible = all.filter(item =>
    (filter === 'all' || (filter === 'completed' ? item.done : !item.done)) &&
    (!subject || item.course === subject) && (!priority || item.priority === priority))
  return <><header className="page-heading"><div><h1>Tasks</h1><p>Track assignments and other work from capture to completion.</p></div>
    {canEdit && <button className="button primary" onClick={() => create('task')}><Plus size={17} /> New task</button>}</header>
    <section className="panel tasks-page">
      <div className="list-toolbar"><div className="segment" aria-label="Task status">
        {Object.entries(options).map(([value, label]) => <button key={value} onClick={() => setFilter(value)} aria-pressed={filter === value} className={filter === value ? 'active' : ''}>{label}</button>)}
      </div><div className="inline"><select aria-label="Filter by subject" value={subject} onChange={e => setSubject(e.target.value)}>
        <option value="">All subjects</option>{subjectCodes.map(code => <option key={code}>{code}</option>)}</select>
        <select aria-label="Filter by priority" value={priority} onChange={e => setPriority(e.target.value)}><option value="">Any priority</option>
          <option value="high">High</option><option value="normal">Normal</option><option value="low">Low</option></select></div></div>
      {visible.length ? <div className="task-list">{visible.map(item => <TaskRow key={item.key || item.id} item={item} today={today}
        onOpen={() => open(item)} onToggle={canEdit && item.source === 'manual' ? () => toggle(item) : null} />)}</div>
        : <Empty icon={ClipboardList} title="No matching tasks" detail="Tasks you create or import will appear here." />}
    </section></>
}
