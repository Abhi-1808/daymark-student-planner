import { useState } from 'react'
import { CalendarDays, CloudDownload, Database, Download, LogOut, Plug, RefreshCw, Upload } from 'lucide-react'
import { dateLabel, dayOf, sources, timeLabel } from './planner.js'
import { ErrorText, Field, SectionTitle, Tag } from './ui.jsx'

const providerDetails = {
  google: ['Google', 'Read Google Calendar events and Google Tasks.'],
  microsoft: ['Microsoft Outlook', 'Read events from Outlook calendars.'],
  bennett: ['Bennett LMS feed', 'Read assignments and course calendar events from a configured LMS calendar link.'],
}

export function Settings({ workspace, request, canEdit, install, logout, refresh, notify }) {
  const [prefs, setPrefs] = useState(workspace.preferences)
  const [source, setSource] = useState('bennett-lms')
  const [file, setFile] = useState(null)
  const [fileKey, setFileKey] = useState(0)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [confirm, setConfirm] = useState(null)
  const [busy, setBusy] = useState('')
  const importSources = [...new Set(workspace.records.map(record => record.source))].filter(value => ['bennett-lms', 'camu', 'csv', 'ics', 'demo'].includes(value))
  const zone = workspace.preferences.timezone

  async function run(label, action) {
    setBusy(label)
    setError('')
    setStatus('')
    try { await action() } catch (cause) { setError(cause.message) } finally { setBusy('') }
  }
  function bind(key) {
    return { value: prefs[key], onChange: event => setPrefs(current => ({
      ...current, [key]: typeof current[key] === 'number' ? Number(event.target.value) : event.target.value,
    })) }
  }
  async function toggleConnection(provider) {
    const result = await request(`/api/connections/${provider}/start`, { method: 'POST' })
    if (result.url) window.location.assign(result.url)
    else setStatus('Connection enabled. Use Sync now to fetch events.')
  }

  return <>
    <header className="page-heading"><div><h1>Settings</h1><p>Manage planning hours, imports, and connected accounts.</p></div>
      {workspace.protected && canEdit && <button className="button secondary" onClick={logout}><LogOut size={16} /> Sign out</button>}</header>
    <div className="study-grid settings-grid">
      <section className="panel inset">
        <SectionTitle title="Planning preferences" />
        <form className="stack" onSubmit={event => {
          event.preventDefault()
          run('preferences', async () => {
            await request('/api/preferences', { method: 'PUT', payload: prefs })
            setStatus('Preferences saved.')
          })
        }}>
          <div className="form-grid"><Field label="Display name"><input required maxLength="60" {...bind('name')} /></Field>
            <Field label="Time zone"><input required {...bind('timezone')} list="time-zones" />
              <datalist id="time-zones">{['Asia/Kolkata', 'UTC', 'Europe/London', 'America/New_York', 'America/Los_Angeles', 'Asia/Singapore'].map(item => <option key={item}>{item}</option>)}</datalist></Field></div>
          <div className="form-grid"><Field label="Start hour (0–23)"><input required type="number" min="0" max="23" {...bind('day_start')} /></Field>
            <Field label="End hour (1–24)"><input required type="number" min="1" max="24" {...bind('day_end')} /></Field></div>
          <Field label="Class and travel buffer (minutes)"><input required type="number" min="0" max="90" {...bind('buffer')} /></Field>
          <button className="button primary fit" disabled={!canEdit || !!busy}>Save preferences</button>
        </form>
      </section>
      <section className="panel inset">
        <SectionTitle title="Import campus data" />
        <form className="stack" onSubmit={event => {
          event.preventDefault()
          if (!file) return
          run('import', async () => {
            const format = file.name.toLowerCase().endsWith('.ics') ? 'ics' : 'csv'
            if (!/\.(csv|ics)$/i.test(file.name)) throw new Error('Choose a CSV or ICS file.')
            const result = await request(`/api/import/${source}?format=${format}`, { method: 'POST', file })
            setStatus(`Processed ${result.count} records from ${file.name}.`)
            setFile(null); setFileKey(value => value + 1)
          })
        }}>
          <Field label="Import as"><select value={source} onChange={e => setSource(e.target.value)}>
            <option value="bennett-lms">Bennett LMS</option><option value="camu">MyCamu</option>
            <option value="csv">General CSV</option><option value="ics">General calendar</option></select></Field>
          <Field label="CSV or ICS file"><input key={fileKey} type="file" accept=".csv,.ics,text/csv,text/calendar" onChange={e => setFile(e.target.files[0])} /></Field>
          <p className="small muted">Import an authorized export or enter timetable and attendance data with the CSV template.</p>
          <div className="inline wrap"><button className="button primary" disabled={!canEdit || !file || !!busy}><Upload size={16} /> Import file</button>
            <a className="button secondary" download="daymark-import-template.csv" href="data:text/csv;charset=utf-8,kind%2Ctitle%2Ccourse%2Cstart%2Cend%2Cdue%2Ccategory%2Cattendance%2Cexternal_id%0A">CSV template</a></div>
        </form>
      </section>
    </div>
    {(error || status) && <div className="space-top" role="status"><ErrorText error={error} />{status && <p className="status-text">{status}</p>}</div>}
    <section className="panel inset space-top">
      <SectionTitle title="Connected accounts" action={canEdit ? 'Refresh status' : undefined} onAction={() => refresh().catch(cause => notify(cause.message))} />
      <div className="provider-list">{Object.entries(providerDetails).map(([provider, [name, description]]) => {
        const state = workspace.connections?.[provider] || {}
        const status = state.error ? 'Sync issue' : state.connected ? 'Connected' : state.available ? 'Ready to connect' : 'Setup required'
        return <div className="provider" key={provider}>
          <span className="metric-icon teal">{provider === 'bennett' ? <CalendarDays size={19} /> : <Plug size={19} />}</span>
          <div className="provider-description"><strong>{name}</strong><span>{description}</span>
            {state.synced && <span>Last synced {dateLabel(dayOf(state.synced, zone))} at {timeLabel(state.synced, zone)}</span>}
            {state.error && <ErrorText error={state.error} />}</div>
          <Tag color={state.error ? 'rose' : state.connected ? 'teal' : 'blue'}>{status}</Tag>
          <div className="inline wrap">
            {state.connected ? <>
              <button className="button secondary" disabled={!canEdit || !!busy || !state.available} onClick={() => run(provider, async () => {
                const res = await request(`/api/connections/${provider}/sync`, { method: 'POST' })
                if (res.error) throw new Error(res.error)
                setStatus(`${name} is up to date.`)
              })}><RefreshCw size={15} /> {busy === provider ? 'Syncing…' : 'Sync now'}</button>
              <button className="text-button" disabled={!canEdit || !!busy} onClick={() => setConfirm({ name, path: `/api/connections/${provider}` })}>Disconnect</button>
            </> : <button className="button secondary" disabled={!canEdit || !!busy || !state.available} onClick={() => run(provider, () => toggleConnection(provider))}>Connect</button>}
          </div>
        </div>
      })}</div>
    </section>
    <section className="panel inset space-top">
      <SectionTitle title="Workspace data" />
      <div className="inline wrap"><a className={`button secondary ${canEdit ? '' : 'disabled'}`} aria-disabled={!canEdit} href={canEdit ? '/api/export.csv' : undefined}><Download size={16} /> Export CSV</a>
        {!importSources.includes('demo') && <button className="button secondary" disabled={!canEdit || !!busy} onClick={() => run('demo', async () => {
          await request('/api/demo', { method: 'POST' }); setStatus('Sample data loaded.')
        })}><Database size={16} /> Load sample data</button>}
        {install && <button className="button secondary" onClick={install}><CloudDownload size={16} /> Install Daymark</button>}</div>
      {importSources.length > 0 && <div className="line-list space-top">{importSources.map(item => <div key={item}>
        <strong>{sources[item]}</strong><button type="button" disabled={!canEdit || !!busy} className="text-button danger-text" onClick={() => setConfirm({ name: sources[item], path: `/api/import/${item}` })}>Remove data</button></div>)}</div>}
      {confirm && <div className="warning-panel space-top"><div><strong>Remove data from {confirm.name}?</strong><p>Local copies for this source will be removed from Daymark.</p>
        <div className="inline wrap"><button className="button secondary" onClick={() => setConfirm(null)}>Cancel</button>
          <button className="button danger" disabled={!!busy} onClick={() => run('remove', async () => {
            await request(confirm.path, { method: 'DELETE' })
            setConfirm(null); setStatus('Source data removed.')
          })}>Confirm removal</button></div></div></div>}
    </section>
  </>
}
