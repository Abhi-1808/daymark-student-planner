const DAY = 86400000
const formatterCache = new Map()
const levels = { high: 0, normal: 1, low: 2 }

export const categories = { class: 'Class', exam: 'Exam', study: 'Study block', personal: 'Personal', holiday: 'Holiday', assignment: 'Assignment' }
export const colors = { teal: 'Teal', blue: 'Blue', violet: 'Violet', amber: 'Amber', rose: 'Rose' }
export const sources = {
  manual: 'Daymark', 'google-calendar': 'Google Calendar', 'google-tasks': 'Google Tasks',
  outlook: 'Outlook', 'bennett-lms': 'Bennett LMS file', 'bennett-feed': 'Bennett LMS feed', camu: 'MyCamu',
  csv: 'CSV import', ics: 'Calendar file', demo: 'Sample data',
}
export const defaults = {
  kind: 'event', title: '', notes: '', course: '', category: 'personal', color: 'teal',
  start: null, end: null, due: null, location: '', priority: 'normal', done: false,
  repeat: 'none', repeat_until: null, skip_days: [], completed_days: [],
  attendance: 'present', minutes: 60, target: 75, busy: true, parent: '',
}

function zoned(value, zone) {
  if (!formatterCache.has(zone)) {
    formatterCache.set(zone, new Intl.DateTimeFormat('en-CA', {
      timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
    }))
  }
  const parts = formatterCache.get(zone).formatToParts(new Date(value))
  return Object.fromEntries(parts.filter(part => part.type !== 'literal').map(part => [part.type, part.value]))
}

export function wall(value, zone) {
  const { year, month, day, hour, minute } = zoned(value, zone)
  return `${year}-${month}-${day}T${hour}:${minute}`
}
export function dayOf(value, zone) {
  return typeof value === 'string' && value.length === 10 ? value : wall(value, zone).slice(0, 10)
}
export function addDays(day, n) {
  return new Date(Date.parse(day) + n * DAY).toISOString().slice(0, 10)
}
export function dayDistance(first, last) {
  return Math.round((Date.parse(last) - Date.parse(first)) / DAY)
}
export function weekStart(day) {
  const offset = (new Date(day).getUTCDay() + 6) % 7
  return addDays(day, -offset)
}
export function monthShift(day, delta) {
  const [year, month, target] = day.split('-').map(Number)
  const last = new Date(Date.UTC(year, month + delta, 0)).getUTCDate()
  return new Date(Date.UTC(year, month - 1 + delta, Math.min(last, target))).toISOString().slice(0, 10)
}
export function dateLabel(day, options = { month: 'short', day: 'numeric' }) {
  return new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', ...options }).format(new Date(day + 'T12:00:00Z'))
}
export function timeLabel(value, zone) {
  return new Intl.DateTimeFormat('en-GB', { timeZone: zone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(value))
}
export function instant(value, zone) {
  const target = Date.parse(value + 'Z')
  if (!Number.isFinite(target)) throw new Error('Enter a valid date and time.')
  for (let guess = target, attempt = 0; attempt < 4; attempt++) {
    const difference = target - Date.parse(wall(guess, zone) + 'Z')
    if (!difference) return guess
    guess += difference
  }
  throw new Error('That time does not exist in the selected time zone.')
}
function boundary(day, hour, zone) {
  return hour === 24 ? boundary(addDays(day, 1), 0, zone) : instant(`${day}T${String(hour).padStart(2, '0')}:00`, zone)
}
function shift(value, offset, zone) {
  if (!offset) return value
  const day = dayOf(value, zone)
  const target = addDays(day, offset)
  if (value.length === 10) return target
  try {
    return new Date(instant(target + wall(value, zone).slice(10), zone)).toISOString()
  } catch {
    return new Date(Date.parse(value) + offset * DAY).toISOString()
  }
}
export function expand(records, first, last, zone) {
  const result = []
  for (const record of records) {
    if (record.kind !== 'event' && record.kind !== 'task') continue
    const anchor = record.kind === 'event' ? dayOf(record.start, zone) : record.due
    if (!anchor) continue
    const allDay = record.kind === 'event' && record.start.length === 10
    const endDay = record.kind === 'event' ? dayOf(record.end, zone) : anchor
    const exclusiveEnd = record.kind === 'event' && (allDay || wall(record.end, zone).endsWith('T00:00'))
    const duration = Math.max(0, dayDistance(anchor, endDay) - Number(exclusiveEnd))
    const step = record.repeat === 'weekly' ? 7 : 1
    const firstOffset = record.repeat === 'none' ? 0 : Math.ceil(Math.max(0, dayDistance(anchor, first) - duration) / step) * step
    const maxOffset = record.repeat === 'none' ? 0 : dayDistance(anchor, record.repeat_until && record.repeat_until < last ? record.repeat_until : last)
    for (let offset = firstOffset; offset <= maxOffset; offset += step) {
      const date = addDays(anchor, offset)
      if (addDays(date, duration) < first || date > last || record.skip_days.includes(date)) continue
      result.push({
        ...record, key: `${record.id}:${date}`, date, lastDay: addDays(date, duration), allDay,
        start: record.start && shift(record.start, offset, zone),
        end: record.end && shift(record.end, offset, zone),
        due: record.due && shift(record.due, offset, zone),
        done: record.repeat === 'none' ? record.done : record.completed_days.includes(date),
      })
    }
  }
  return result.sort((a, b) => a.date.localeCompare(b.date) || (a.start || '').localeCompare(b.start || '') || a.title.localeCompare(b.title))
}
export function taskOrder(tasks) {
  return [...tasks].sort((a, b) => Number(a.done) - Number(b.done) ||
    (a.due || '9999').localeCompare(b.due || '9999') || levels[a.priority] - levels[b.priority] || a.title.localeCompare(b.title))
}
export function includesDay(item, day) {
  return item.date <= day && item.lastDay >= day
}
export function inputRecord(item) {
  return Object.fromEntries(Object.keys(defaults).map(key => [key, item[key] ?? defaults[key]]))
}
function titleKey(title) {
  return title.normalize('NFKC').toLowerCase().replace(/\b(lecture|tutorial|practical|class|lab)\b/g, ' ').replace(/[^\p{L}\p{N}]+/gu, ' ').trim()
}
function roomKey(room) {
  return room.toLowerCase().replace(/\b(room|block)\b/g, '').replace(/[^a-z0-9]/g, '')
}
export function duplicateState(records, dismissed) {
  const slots = new Map()
  for (const row of records) {
    if (row.kind !== 'event' || !['camu', 'google-calendar'].includes(row.source)) continue
    const title = titleKey(row.title)
    if (!title || row.start.length === 10) continue
    const key = JSON.stringify([row.start, row.end])
    const group = slots.get(key) || { camu: [], google: [] }
    group[row.source === 'camu' ? 'camu' : 'google'].push(row)
    slots.set(key, group)
  }
  const matches = new Map()
  const signatures = new Map(dismissed.map(row => [row.id, row]))
  for (const group of slots.values()) {
    for (const copy of group.google) {
      const mates = group.camu.filter(row => titleKey(row.title) === titleKey(copy.title) &&
        (!row.location || !copy.location || roomKey(row.location) === roomKey(copy.location)) &&
        (!row.course || !copy.course || row.course.toLowerCase() === copy.course.toLowerCase()))
      if (mates.length !== 1) continue
      const [mate] = mates
      const expected = JSON.stringify([copy, mate].map(item => [item.title, item.start, item.end, item.location, item.course]))
      const decision = signatures.get(copy.id)
      matches.set(copy.id, { copy, mate, expected, hidden: decision?.mate === mate.id && decision.expected === expected })
    }
  }
  const pairs = [...matches.values()]
  return { pairs, hidden: new Set(pairs.filter(pair => pair.hidden).map(pair => pair.copy.id)), copies: new Set(matches.keys()) }
}
function interval(item, zone) {
  return item.allDay
    ? [boundary(item.start, 0, zone), boundary(item.end, 0, zone)]
    : [Date.parse(item.start), Date.parse(item.end)]
}
export function conflicts(items, zone, gap, copies = new Set()) {
  const events = items.filter(item => item.kind === 'event' && item.busy && !item.allDay && !copies.has(item.id))
    .map(item => ({ item, start: Date.parse(item.start), end: Date.parse(item.end) }))
    .sort((a, b) => a.start - b.start)
  const result = []
  for (let i = 0; i < events.length; i++) {
    const a = events[i]
    for (let j = i + 1; j < events.length; j++) {
      const b = events[j]
      const minutes = Math.floor((b.start - a.end) / 60000)
      if (minutes >= gap) break
      const travel = a.item.location && b.item.location && roomKey(a.item.location) !== roomKey(b.item.location)
      if (minutes < 0 || travel) result.push({ first: a.item, second: b.item, minutes })
    }
  }
  return result
}
export function freeSlots(events, day, prefs, floor = 0) {
  const { timezone: zone, day_start: startHour, day_end: endHour, buffer } = prefs
  let cursor = Math.max(boundary(day, startHour, zone), Math.ceil(floor / 300000) * 300000)
  const limit = boundary(day, endHour, zone)
  const intervals = events.filter(item => item.kind === 'event' && item.busy && item.category !== 'holiday')
    .filter(item => includesDay(item, day) || (!item.allDay && (
      Math.abs(dayDistance(item.lastDay, day)) <= 1 || Math.abs(dayDistance(item.date, day)) <= 1
    )))
    .map(item => {
      const [start, end] = interval(item, zone)
      const pad = item.allDay ? 0 : (item.category === 'study' ? 5 : buffer) * 60000
      return [start - pad, end + pad]
    }).sort((a, b) => a[0] - b[0])
  const slots = []
  for (const [start, end] of intervals) {
    if (end <= cursor) continue
    if (start >= limit) break
    if (start > cursor) slots.push({ start: cursor, end: start })
    cursor = Math.max(cursor, end)
  }
  if (cursor < limit) slots.push({ start: cursor, end: limit })
  return slots
}
export function slotMinutes(slots) {
  return slots.reduce((total, slot) => total + Math.floor((slot.end - slot.start) / 60000), 0)
}
export function buildPlan(tasks, items, first, last, prefs, now = Date.now(), spread = false) {
  const slots = []
  for (let day = first; day <= last; day = addDays(day, 1)) {
    slots.push(...freeSlots(items, day, prefs, now + 300000).map(slot => ({ ...slot, day })))
  }
  const blocks = []
  const unfinished = []
  for (const task of taskOrder(tasks)) {
    const scheduled = items.filter(item => item.category === 'study' && item.parent && item.parent === task.id)
      .reduce((sum, item) => sum + (Date.parse(item.end) - Date.parse(item.start)) / 60000, 0)
    let remaining = Math.max(0, Math.ceil(task.minutes - scheduled))
    let previousDay = ''
    while (remaining > 0 && blocks.length < 150) {
      const eligible = slots.filter(slot => (!task.due || slot.day <= task.due) && slot.end - slot.start >= Math.min(15, remaining) * 60000)
      const slot = (spread && eligible.find(candidate => candidate.day > previousDay)) || eligible[0]
      if (!slot) break
      const minutes = Math.min(45, remaining, Math.floor((slot.end - slot.start) / 60000 / 5) * 5 || remaining)
      const count = Math.min(minutes, Math.floor((slot.end - slot.start) / 60000))
      const end = slot.start + count * 60000
      blocks.push(inputRecord({
        title: task.title, category: 'study', color: 'violet', course: task.course,
        start: new Date(slot.start).toISOString(), end: new Date(end).toISOString(), parent: task.id || '',
      }))
      remaining -= count
      previousDay = slot.day
      slot.start = end + 300000
    }
    if (remaining) unfinished.push({ title: task.title, minutes: remaining })
  }
  return { blocks: blocks.sort((a, b) => a.start.localeCompare(b.start)), unfinished }
}
export function attendanceSummary(records, course) {
  const counts = { present: 0, absent: 0, excused: 0 }
  for (const record of records) if (record.kind === 'attendance' && record.course.toLowerCase() === course.course.toLowerCase()) counts[record.attendance]++
  const total = counts.present + counts.absent
  return { ...counts, total, percent: total ? Math.round(counts.present / total * 1000) / 10 : null }
}
export function quickAdd(raw, today, zone) {
  let title = raw.trim()
  if (!title) throw new Error('Enter something to add.')
  let due = null, minutes = 60, priority = 'normal'
  title = title.replace(/\s+p([123])$/i, (_, level) => {
    priority = { 1: 'high', 2: 'normal', 3: 'low' }[level]
    return ''
  })
  title = title.replace(/\s+for\s+(?=[0-9])(?:(\d+)\s*h\s*)?(?:(\d+)\s*m)?\b/i, (match, hours, mins) => {
    if (!hours && !mins) return match
    minutes = Math.max(15, Math.min(480, Number(hours || 0) * 60 + Number(mins || 0)))
    return ''
  })
  const named = 'today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday'
  const weekdays = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
  title = title.replace(new RegExp(`\\s+(?:on\\s+)?(\\d{4}-\\d{2}-\\d{2}|in\\s+\\d{1,3}\\s+days?|(?:${named}))\\b`, 'i'), (_, phrase) => {
    const word = phrase.toLowerCase()
    if (word === 'today' || word === 'tomorrow') due = addDays(today, Number(word === 'tomorrow'))
    else if (word.startsWith('in ')) due = addDays(today, Number(word.match(/\d+/)[0]))
    else if (weekdays.includes(word)) due = addDays(today, (weekdays.indexOf(word) + 7 - new Date(today).getUTCDay()) % 7)
    else {
      const date = new Date(word)
      if (!Number.isFinite(+date) || date.toISOString().slice(0, 10) !== word) throw new Error('Enter a real calendar date.')
      due = word
    }
    return ''
  })
  let clock
  title = title.replace(/\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?(?=\s|$)/i, (_, hours, mins, half) => {
    let h = Number(hours)
    const m = Number(mins || 0)
    if ((!mins && !half && h < 13) || h > 23 || m > 59 || (half && (h < 1 || h > 12))) {
      throw new Error('Use a clear time, such as 4 pm or 16:00.')
    }
    if (half) h = h % 12 + (half.toLowerCase() === 'pm' ? 12 : 0)
    clock = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
    return ''
  })
  title = title.trim()
  if (!title) throw new Error('Add a title for this item.')
  if (!clock) return { ...defaults, kind: 'task', title, due, minutes, priority }
  const start = instant(`${due || today}T${clock}`, zone)
  return { ...defaults, title, due: null, start: new Date(start).toISOString(),
    end: new Date(start + minutes * 60000).toISOString(), minutes, priority, category: 'study', color: 'violet' }
}
