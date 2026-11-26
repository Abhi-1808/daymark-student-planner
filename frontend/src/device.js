import { addDays, dayOf, expand, instant } from './planner.js'

export function setting(key, fallback) {
  try { return localStorage.getItem(key) || fallback } catch { return fallback }
}
export function remember(key, value) {
  try { localStorage.setItem(key, value) } catch { /* optional device preferences */ }
}
export function applyTheme(theme) {
  document.documentElement.dataset.theme = ['dark', 'light'].includes(theme) ? theme : 'system'
}

export async function remind(records, zone, now) {
  if (setting('daymark-device-alerts', 'off') !== 'on' || !('Notification' in window) ||
      Notification.permission !== 'granted') return
  const today = dayOf(now, zone)
  const recent = expand(records, addDays(today, -1), addDays(today, 1), zone)
  for (const item of recent) {
    if (item.reminder === null || item.done) continue
    const start = item.kind === 'task' || item.allDay
      ? instant(item.date + 'T09:00', zone) : Date.parse(item.start)
    const reminder = start - item.reminder * 60000
    if (reminder > now || reminder < now - 90000) continue
    const tag = `daymark:${item.key}:${item.reminder}`
    if (setting('daymark-last-alerts', '').split('|').includes(tag)) continue
    remember('daymark-last-alerts', [...setting('daymark-last-alerts', '').split('|').slice(-149), tag].join('|'))
    try {
      const registration = await navigator.serviceWorker?.getRegistration()
      const options = { tag, body: item.kind === 'task' ? 'Task due today' : 'Upcoming event', icon: '/icon-192.png' }
      if (registration?.active) await registration.showNotification(item.title, options)
      else new Notification(item.title, options)
    } catch { /* The browser may restrict notifications in this context. */ }
  }
}
