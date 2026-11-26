import assert from 'node:assert/strict'
import { test } from 'node:test'
import { addDays, attendanceSummary, buildPlan, conflicts, dayOf, duplicateState, expand, freeSlots,
  includesDay, instant, quickAdd, slotMinutes, timeLabel } from '../frontend/src/planner.js'
import { defaults } from '../frontend/src/planner.js'

const zone = 'Asia/Kolkata'
const day = '2026-11-26'
const prefs = { timezone: zone, day_start: 9, day_end: 13, buffer: 10 }
const iso = (time, date = day) => new Date(instant(`${date}T${time}`, zone)).toISOString()
const event = (start, end, options = {}) => ({
  ...defaults, id: start, source: 'manual', title: 'Class', start: iso(start), end: iso(end), ...options,
})

test('monthly and daily views show every occupied day except a midnight end', () => {
  const record = event('09:00', '11:00', { start: day, end: addDays(day, 2) })
  const rows = expand([record], day, addDays(day, 2), zone)
  assert.equal(rows[0].allDay, true)
  assert.equal(includesDay(rows[0], addDays(day, 1)), true)
  assert.equal(includesDay(rows[0], addDays(day, 2)), false)
})

test('weekly recurrence keeps wall-clock hours after daylight saving changes', () => {
  const timezone = 'America/New_York'
  const result = expand([event('09:00', '10:00', { repeat: 'weekly',
    start: '2026-03-01T14:00:00.000Z', end: '2026-03-01T15:00:00.000Z',
    skip_days: ['2026-03-08'], repeat_until: '2026-03-15',
  })], '2026-03-01', '2026-03-29', timezone)
  assert.equal(result.length, 2)
  assert.equal(result[1].start, '2026-03-15T13:00:00.000Z')
  assert.equal(timeLabel(result[1].start, timezone), '09:00')
})

test('recurring task completion is recorded per occurrence', () => {
  const rows = expand([{ ...defaults, id: 'rec', kind: 'task', title: 'Review', due: day,
    repeat: 'daily', completed_days: [addDays(day, 1)],
  }], day, addDays(day, 2), zone)
  assert.deepEqual(rows.map(item => item.done), [false, true, false])
})

test('free slots include travel buffer and preserve free calendar events', () => {
  const items = expand([event('10:00', '11:00'), event('12:00', '13:00', { busy: false })], day, day, zone)
  const slots = freeSlots(items, day, prefs)
  assert.deepEqual(slots.map(slot => [timeLabel(slot.start, zone), timeLabel(slot.end, zone)]),
    [['09:00', '09:50'], ['11:10', '13:00']])
  assert.equal(slotMinutes(slots), 160)
})

test('conflict detection handles overlaps, short room changes, and duplicate suggestions', () => {
  const rows = [event('09:00', '10:00', { location: 'Room 101' }),
    event('10:03', '11:00', { location: 'Room 102' }),
    event('10:01', '10:15', { id: 'import', location: 'Room 101' })]
  const items = expand(rows, day, day, zone)
  assert.deepEqual(conflicts(items, zone, 10, new Set(['import'])).map(item => item.minutes), [3])
  assert.equal(conflicts(items, zone, 10).some(item => item.minutes < 0), true)
})

test('duplicate review hides only the reviewed copy and reopens changed events', () => {
  const records = [
    event('10:00', '11:00', { id: 'a', title: 'DBMS lecture', source: 'camu-feed', location: 'Room 3' }),
    event('10:00', '11:00', { id: 'b', title: 'DBMS', source: 'google-calendar', location: '3' }),
  ]
  const listed = duplicateState(records, []).pairs[0]
  assert.equal(listed.hidden, false)
  const decision = [{ id: 'b', mate: 'a', expected: listed.expected }]
  assert.deepEqual([...duplicateState(records, decision).hidden], ['b'])
  records[1].location = 'Room 4'
  assert.equal(duplicateState(records, decision).pairs.length, 0)
})

test('study plan respects occupied time, deadlines, existing work, and five-minute breaks', () => {
  const items = expand([event('11:00', '12:00'),
    event('09:30', '10:00', { category: 'study', parent: 'task' })], day, day, zone)
  const task = { ...defaults, id: 'task', title: 'Learn SQL', kind: 'task', due: day, minutes: 100 }
  const result = buildPlan([task], items, day, addDays(day, 2), prefs, 1)
  assert.equal(result.unfinished.length, 0)
  assert.equal(result.blocks.reduce((total, block) => total + (+new Date(block.end) - +new Date(block.start)) / 60000, 0), 70)
  assert.equal(result.blocks.every(block => dayOf(block.start, zone) === day), true)
  for (let i = 1; i < result.blocks.length; i++) {
    assert.ok(+new Date(result.blocks[i].start) - +new Date(result.blocks[i - 1].end) >= 300000)
  }
})

test('exam plans spread long topics across available dates', () => {
  const result = buildPlan([{ ...defaults, kind: 'task', title: 'Topics', minutes: 120 }], [],
    day, addDays(day, 2), prefs, 1, true)
  assert.deepEqual(result.blocks.map(block => dayOf(block.start, zone)), [day, addDays(day, 1), addDays(day, 2)])
})

test('quick add recognizes relative dates, duration, clock time, and priority', () => {
  const item = quickAdd('Review SQL tomorrow at 4 pm for 1h 30m p1', day, zone)
  assert.equal(item.title, 'Review SQL')
  assert.equal(item.minutes, 90)
  assert.equal(item.priority, 'high')
  assert.equal(timeLabel(item.start, zone), '16:00')
  assert.equal(dayOf(item.start, zone), addDays(day, 1))
  assert.equal(quickAdd('Read notes in 3 days', day, zone).due, addDays(day, 3))
  assert.throws(() => quickAdd('Study at 4', day, zone), /clear time/)
  assert.throws(() => quickAdd('Study on 2026-02-31', day, zone), /real calendar date/)
})

test('attendance excludes excused outcomes', () => {
  const rows = ['present', 'present', 'absent', 'excused'].map(attendance => ({
    kind: 'attendance', course: 'DBMS', attendance,
  }))
  assert.equal(attendanceSummary(rows, { course: 'dbms' }).percent, 66.7)
})
