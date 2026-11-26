import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowRight, BookOpen, CalendarDays, CalendarPlus, Check, ChevronDown, CircleHelp, ClipboardList,
  CloudOff, Command, CopyCheck, Menu, Plus, Search, Settings2, Sunrise, X, Zap,
} from 'lucide-react'
import { api, clearCache, readCache, writeCache } from './api.js'
import { CalendarView } from './calendar.jsx'
import { makeDraft, RecordEditor } from './editor.jsx'
import { addDays, categories, conflicts, dateLabel, dayOf, duplicateState, expand, inputRecord, quickAdd, sources } from './planner.js'
import { Settings } from './settings.jsx'
import { Study } from './study.jsx'
import { Tasks } from './tasks.jsx'
import { Today } from './today.jsx'
import { Empty, ErrorText, EventRow, Field, IconButton, Modal, Tag } from './ui.jsx'

const pages = {
  today: { label: 'Today', icon: Sunrise },
  calendar: { label: 'Calendar', icon: CalendarDays },
  tasks: { label: 'Tasks', icon: ClipboardList },
  study: { label: 'Study', icon: BookOpen },
  settings: { label: 'Settings', icon: Settings2 },
}
const getPage = () => {
  const route = location.hash.slice(1)
  return Object.hasOwn(pages, route) ? route : 'today'
}
function cachedFilters() {
  try {
    const data = JSON.parse(localStorage.getItem('daymark-calendar-filters') || '[]')
    return Array.isArray(data) ? data.filter(value => typeof value === 'string') : []
  } catch { return [] }
}

export function Brand() {
  return <span className="brand"><img src="/daymark.svg" alt="" width="36" height="36" /><strong>daymark<span>.</span></strong></span>
}

function WelcomeScreen({ login, locked, error, retry }) {
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState('')
  return <div className="welcome-screen"><section className="panel inset">
    <Brand />
    {locked ? <><h1>Sign in to Daymark</h1><p className="muted">Enter your workspace password.</p>
      <form className="stack space-top" onSubmit={async event => {
        event.preventDefault()
        setBusy(true); setProblem('')
        try { await login(password) } catch (reason) { setProblem(reason.message) } finally { setBusy(false) }
      }}>
        <Field label="Workspace password"><input type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} autoFocus /></Field>
        <ErrorText error={problem} /><button className="button primary" disabled={busy}>Sign in <ArrowRight size={17} /></button>
      </form></>
      : error ? <><h1>Daymark is unavailable</h1><ErrorText error={error} /><button className="button primary space-top" onClick={retry}>Try again</button></>
        : <p className="muted space-top" role="status">Opening your workspace…</p>}
  </section></div>
}

function SearchPanel({ records, close, open }) {
  const [query, setQuery] = useState('')
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  const matches = words.length ? records.filter(item => words.every(word => [item.title, item.notes, item.course, item.location, sources[item.source]]
    .some(text => text?.toLowerCase().includes(word)))).slice(0, 35) : []
  return <Modal title="Search your workspace" onClose={close}>
    <div className="form-body">
      <label className="search-input"><Search size={18} /><input type="search" value={query} autoFocus placeholder="Search events, tasks, and subjects" onChange={e => setQuery(e.target.value)} /></label>
      {words.length > 0 && (!matches.length ? <Empty icon={Search} title="No results" /> : <div className="line-list search-results">{matches.map(item =>
        <button key={item.id} onClick={() => open(item)}><div><strong>{item.title}</strong><small>{item.course || sources[item.source]}</small></div>
          <Tag color={item.color}>{item.kind === 'event' ? categories[item.category] : item.kind === 'course' ? 'Subject' : item.kind}</Tag></button>)}</div>)}
    </div>
  </Modal>
}

function QuickPanel({ today, zone, close, preview }) {
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  return <Modal title="Quick Add" onClose={close}><form onSubmit={event => {
    event.preventDefault()
    try { preview(quickAdd(text, today, zone)) } catch (reason) { setError(reason.message) }
  }}>
    <div className="form-body"><Field label="What do you need to do?"><input autoFocus required value={text} maxLength={280}
      placeholder="Review SQL tomorrow at 4 pm for 45m" onChange={event => setText(event.target.value)} /></Field>
      <p className="small muted">Use a date or weekday, a time, an estimate, and p1, p2, or p3 for priority.</p>
      <ErrorText error={error} /></div>
    <div className="dialog-actions"><button type="button" className="button secondary" onClick={close}>Cancel</button><button className="button primary">Review draft</button></div>
  </form></Modal>
}

function DuplicatePanel({ matches, close, canEdit, revision, zone, request }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  return <Modal title="Review duplicate events" onClose={close}>
    <div className="form-body">
      <p className="small muted">Review matches between MyCamu and Google Calendar. Hiding a copy only affects Daymark.</p>
      <ErrorText error={error} />
      {matches.pairs.length ? <div className="duplicate-list">{matches.pairs.map(pair => <article key={pair.copy.id}>
        <EventRow item={pair.mate} zone={zone} withDate />
        <p className="small muted">MyCamu · Google Calendar</p>
        <button className="button secondary" disabled={!canEdit || !!busy} onClick={async () => {
          setBusy(pair.copy.id); setError('')
          try {
            await request(`/api/duplicates/${pair.copy.id}`, pair.hidden ? { method: 'DELETE' } :
              { method: 'PUT', payload: { revision, mate: pair.mate.id, expected: pair.expected } })
          } catch (reason) { setError(reason.message) } finally { setBusy('') }
        }}>{pair.hidden ? 'Restore Google copy' : 'Hide Google copy'}</button>
      </article>)}</div> : <Empty icon={CopyCheck} title="No duplicate events to review" />}
    </div>
  </Modal>
}

export function App() {
  const [workspace, setWorkspace] = useState(null)
  const [locked, setLocked] = useState(false)
  const [loadingError, setLoadingError] = useState('')
  const [offline, setOffline] = useState(0)
  const [now, setNow] = useState(Date.now)
  const [page, setPage] = useState(getPage)
  const [day, setDay] = useState(null)
  const [mode, setMode] = useState('month')
  const [dialog, setDialog] = useState(null)
  const [drawer, setDrawer] = useState(false)
  const [menu, setMenu] = useState(false)
  const [toast, setToast] = useState(null)
  const [filters, setFilters] = useState(cachedFilters)
  const [installPrompt, setInstallPrompt] = useState(null)
  const reqId = useRef(0)
  const cacheDate = useRef(0)
  const visible = useRef(null)
  const createMenu = useRef(null)
  const toastTimer = useRef(null)
  const zone = workspace?.preferences.timezone || 'Asia/Kolkata'
  const today = dayOf(now, zone)
  const focus = day || today
  const canEdit = !offline
  const matches = useMemo(() => duplicateState(workspace?.records || [], workspace?.dismissed || []), [workspace])
  const records = useMemo(() => (workspace?.records || []).filter(item => !matches.hidden.has(item.id)), [workspace, matches])
  const courses = useMemo(() => {
    const options = new Map()
    for (const item of records.filter(item => item.course && item.kind !== 'course')) {
      const key = item.course.toLowerCase()
      if (!options.has(key)) options.set(key, { id: key, course: item.course, title: item.course, color: item.color, target: 75 })
    }
    for (const item of records.filter(item => item.course && item.kind === 'course')) options.set(item.course.toLowerCase(), item)
    return [...options.values()].sort((a, b) => a.course.localeCompare(b.course))
  }, [records])

  const notify = useCallback((text, success = false) => {
    setToast({ text, success })
    clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(null), 5000)
  }, [])

  const refresh = useCallback(async () => {
    const id = ++reqId.current
    try {
      const data = await api('/api/workspace')
      if (id !== reqId.current) return
      const changed = visible.current?.revision !== data.revision ||
        JSON.stringify(visible.current?.connections) !== JSON.stringify(data.connections)
      if (changed || !cacheDate.current || Date.now() - cacheDate.current > 60000) {
        cacheDate.current = Date.now()
        void writeCache(data)
      }
      visible.current = data
      setWorkspace(current => !current || changed ? data : current)
      setOffline(0)
      setLocked(false)
      setLoadingError('')
    } catch (error) {
      if (id !== reqId.current) return
      if (error.status === 401) {
        visible.current = null
        cacheDate.current = 0
        setWorkspace(null)
        setLocked(true)
        setDialog(null)
        setOffline(0)
        await clearCache()
      } else {
        const cached = await readCache()
        if (id !== reqId.current) return
        if (cached?.workspace) {
          visible.current = cached.workspace
          setWorkspace(cached.workspace); setOffline(cached.saved)
        } else if (visible.current) {
          setOffline(cacheDate.current || Date.now())
        } else {
          setLoadingError('Start the Daymark server, then try again.')
        }
      }
    }
  }, [])

  useEffect(() => {
    const query = new URLSearchParams(location.search)
    const connection = query.get('connection')
    if (connection) {
      notify({ connected: 'Source connected. The initial sync may take a moment.', declined: 'Connection was canceled.', failed: 'Connection failed. Check the provider settings.' }[connection] || 'Connection updated.', connection === 'connected')
      history.replaceState(null, '', location.pathname + location.hash)
    }
    const hash = () => { setPage(getPage()); setDrawer(false); setMenu(false) }
    const onInstall = event => { event.preventDefault(); setInstallPrompt(event) }
    const onKey = event => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        if (visible.current) setDialog({ type: 'search' })
      }
    }
    const foreground = () => { if (document.visibilityState === 'visible') void refresh() }
    void refresh()
    const timer = setInterval(() => { setNow(Date.now()); foreground() }, 30000)
    window.addEventListener('hashchange', hash)
    window.addEventListener('beforeinstallprompt', onInstall)
    window.addEventListener('keydown', onKey)
    window.addEventListener('online', refresh)
    window.addEventListener('offline', refresh)
    document.addEventListener('visibilitychange', foreground)
    return () => {
      clearInterval(timer); clearTimeout(toastTimer.current)
      window.removeEventListener('hashchange', hash)
      window.removeEventListener('beforeinstallprompt', onInstall)
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('online', refresh)
      window.removeEventListener('offline', refresh)
      document.removeEventListener('visibilitychange', foreground)
    }
  }, [notify, refresh])

  useEffect(() => { try { localStorage.setItem('daymark-calendar-filters', JSON.stringify(filters)) } catch { /* storage is optional */ } }, [filters])
  useEffect(() => {
    if (!menu) return
    const outside = event => { if (!createMenu.current?.contains(event.target)) setMenu(false) }
    const escape = event => { if (event.key === 'Escape') setMenu(false) }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape) }
  }, [menu])

  function nav(route, view) {
    if (view) setMode(view)
    setPage(route); setDrawer(false); setMenu(false)
    if (location.hash !== '#' + route) location.hash = route
  }
  function open(item) {
    setDialog({ type: 'record', record: { ...item, original: workspace.records.find(row => row.id === item.id) } })
  }
  function create(kind, data = {}) {
    if (!canEdit) return
    setMenu(false)
    setDialog({ type: 'record', record: makeDraft(kind, page === 'calendar' ? focus : today, zone, data) })
  }
  async function request(path, options) {
    if (!canEdit) throw new Error('Reconnect to update your workspace.')
    try {
      const result = await api(path, options)
      await refresh()
      return result
    } catch (error) {
      if (error.status === 401 || !error.status) await refresh()
      throw error
    }
  }
  async function save(body, id) {
    await request(id ? `/api/records/${id}` : '/api/records', { method: id ? 'PUT' : 'POST', payload: body })
    notify('Saved to Daymark.', true)
  }
  async function remove(id) {
    await request(`/api/records/${id}`, { method: 'DELETE' })
    notify('Item deleted.', true)
  }
  async function skip(item) {
    const original = item.original
    await save({ ...inputRecord(original), skip_days: [...new Set([...original.skip_days, item.date])] }, item.id)
  }
  async function toggle(item) {
    const original = workspace.records.find(row => row.id === item.id)
    const body = inputRecord(original)
    if (item.date && body.repeat !== 'none') {
      body.completed_days = item.done ? body.completed_days.filter(date => date !== item.date) : [...new Set([...body.completed_days, item.date])]
    } else body.done = !item.done
    try { await request(`/api/records/${item.id}`, { method: 'PUT', payload: body }) } catch (error) { notify(error.message) }
  }
  async function sample() {
    try { await request('/api/demo', { method: 'POST' }); notify('Sample data loaded.', true) } catch (error) { notify(error.message) }
  }
  async function logout() {
    try {
      await api('/api/logout', { method: 'POST' })
      await refresh()
    } catch (error) { notify(error.message) }
  }
  function checkWarnings(body, id) {
    if (body.kind !== 'event' || !body.busy || body.start.length === 10) return []
    const first = dayOf(body.start, zone)
    const last = body.repeat === 'none' ? dayOf(body.end, zone)
      : body.repeat_until && body.repeat_until < addDays(first, 56) ? body.repeat_until : addDays(first, 56)
    const proposal = '__draft'
    const expanded = expand([...workspace.records.filter(item => item.id !== id), { ...body, id: proposal }],
      addDays(first, -1), addDays(last, 1), zone)
    return conflicts(expanded, zone, workspace.preferences.buffer, matches.copies)
      .filter(pair => [pair.first.id, pair.second.id].includes(proposal))
      .map(pair => ({ title: pair.first.id === proposal ? pair.second.title : pair.first.title, minutes: pair.minutes }))
  }

  if (!workspace) return <WelcomeScreen locked={locked} error={loadingError} retry={refresh} login={async password => {
    await api('/api/login', { method: 'POST', payload: { password } })
    await refresh()
  }} />

  const selected = pages[page]
  const count = matches.pairs.filter(pair => !pair.hidden).length
  const close = () => setDialog(null)
  const common = { today, now, open, toggle, create, canEdit }
  return <div className="shell">
    {drawer && <button className="drawer-backdrop" aria-label="Close navigation" onClick={() => setDrawer(false)} />}
    <aside className={`sidebar ${drawer ? 'open' : ''}`}>
      <button className="brand-link" onClick={() => nav('today')} aria-label="Daymark home"><Brand /></button>
      <div className="create-wrap" ref={createMenu}>
        <button className="create-button" aria-expanded={menu} disabled={!canEdit} onClick={() => setMenu(value => !value)}>
          <Plus size={18} /> Create <ChevronDown size={15} /></button>
        {menu && <div className="create-menu">
          <button onClick={() => create('event')}><CalendarPlus size={16} /> New event</button>
          <button onClick={() => create('task')}><ClipboardList size={16} /> New task</button>
          <button onClick={() => { setDialog({ type: 'quick' }); setMenu(false) }}><Zap size={16} /> Quick Add</button>
        </div>}
      </div>
      <nav className="navigation" aria-label="Workspace">
        {Object.entries(pages).map(([key, { label, icon: Icon }]) => <a className={`${key === page ? 'active' : ''} ${key === 'settings' ? 'last-link' : ''}`}
          href={`#${key}`} key={key} aria-current={page === key ? 'page' : undefined} onClick={event => { event.preventDefault(); nav(key) }}>
          <Icon size={19} strokeWidth={1.8} /><span>{label}</span>
        </a>)}
      </nav>
      <div className="sidebar-foot"><span className="avatar">{workspace.preferences.name.slice(0, 1).toUpperCase()}</span>
        <div><strong>{workspace.preferences.name}</strong><span>Personal workspace</span></div>
      </div>
    </aside>
    <div className="main-shell">
      <header className="topbar">
        <div className="topbar-title"><IconButton className="mobile-nav" label="Open navigation" icon={Menu} onClick={() => setDrawer(true)} />
          <selected.icon size={17} /><span>{selected.label}</span></div>
        <div className="topbar-actions">
          {count > 0 && <button className="button review-button" onClick={() => setDialog({ type: 'duplicates' })}><CopyCheck size={16} /> <span>Review</span> {count}</button>}
          <button className="search-button" onClick={() => setDialog({ type: 'search' })}><Search size={17} /><span>Search anything</span><kbd><Command size={11} /> K</kbd></button>
          <IconButton className="help-button" icon={CircleHelp} label="Workspace help" onClick={() => setDialog({ type: 'help' })} />
        </div>
      </header>
      <main className="content">
        {offline > 0 && <div className="offline-banner" role="status"><CloudOff size={18} />
          <span>Offline view · Last loaded {new Date(offline).toLocaleString()}</span><button className="text-button" onClick={refresh}>Retry</button></div>}
        {page === 'today' && <Today {...common} workspace={workspace} visibleRecords={records} nav={nav} setDay={setDay} sample={sample} />}
        {page === 'calendar' && <CalendarView {...common} day={focus} setDay={setDay} mode={mode} setMode={setMode} records={records}
          prefs={workspace.preferences} hidden={filters} setHidden={setFilters} />}
        {page === 'tasks' && <Tasks {...common} records={records} zone={zone} />}
        {page === 'study' && <Study {...common} workspace={workspace} courses={courses} matches={matches} confirm={async preview => {
          const result = await request('/api/plan', { method: 'POST', payload: { revision: preview.revision, blocks: preview.blocks } })
          notify(`${result.count} study blocks added.`, true)
        }} />}
        {page === 'settings' && <Settings workspace={workspace} request={request} canEdit={canEdit} logout={logout} refresh={refresh} notify={notify}
          install={installPrompt && (async () => { await installPrompt.prompt(); setInstallPrompt(null) })} />}
      </main>
    </div>
    {dialog?.type === 'search' && <SearchPanel records={workspace.records} close={close} open={open} />}
    {dialog?.type === 'record' && <RecordEditor key={dialog.record.key || dialog.record.id || dialog.record.kind} record={dialog.record}
      zone={zone} courses={courses} close={close} save={save} remove={remove} skip={skip} canEdit={canEdit} checkWarnings={checkWarnings} />}
    {dialog?.type === 'quick' && <QuickPanel today={today} zone={zone} close={close} preview={record => setDialog({ type: 'record', record })} />}
    {dialog?.type === 'duplicates' && <DuplicatePanel matches={matches} close={close} request={request} canEdit={canEdit} revision={workspace.revision} zone={zone} />}
    {dialog?.type === 'help' && <Modal title="Workspace help" onClose={close}>
      <div className="form-body help-content"><h3>Find anything</h3><p>Open search with Ctrl+K or ⌘K.</p>
      <h3>Bring your calendars together</h3><p>Use Settings to connect Google or Outlook, or import your campus timetable.</p>
      <h3>Review matches</h3><p>Inspect imported copies and choose which copies to hide in Daymark.</p>
      <button className="button secondary fit" onClick={() => setDialog({ type: 'duplicates' })}><CopyCheck size={16} /> Review duplicates</button></div>
    </Modal>}
    {toast && <div className={`toast ${toast.success ? 'success' : ''}`} role="status">{toast.success && <Check size={18} />}<span>{toast.text}</span>
      <IconButton icon={X} label="Dismiss message" onClick={() => setToast(null)} /></div>}
  </div>
}
