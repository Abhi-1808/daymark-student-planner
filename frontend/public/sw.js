const CACHE = 'daymark-shell-__DAYMARK_BUILD__'
const STATIC = ['/', '/manifest.webmanifest', '/daymark.svg', '/icon-192.png', '/icon-512.png']

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const response = await fetch('/', { cache: 'reload' })
    if (!response.ok) throw new Error('App shell unavailable')
    const html = await response.clone().text()
    const assets = [...html.matchAll(/(?:src|href)="(\/assets\/[^"]+)"/g)].map(match => match[1])
    const cache = await caches.open(CACHE)
    await cache.put('/', response)
    await cache.addAll([...STATIC.slice(1), ...new Set(assets)])
    for (const asset of assets.filter(path => path.endsWith('.css'))) {
      const css = await (await cache.match(asset)).text()
      const fonts = [...css.matchAll(/url\(["']?(\/assets\/[^)"']+\.woff2?)["']?\)/g)].map(match => match[1])
      if (fonts.length) await cache.addAll([...new Set(fonts)])
    }
    await self.skipWaiting()
  })())
})

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) {
      if (name.startsWith('daymark-shell-') && name !== CACHE) await caches.delete(name)
    }
    await self.clients.claim()
  })())
})

self.addEventListener('fetch', event => {
  const request = event.request
  const url = new URL(request.url)
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return
  if (!STATIC.includes(url.pathname) && !url.pathname.startsWith('/assets/')) return
  event.respondWith((async () => {
    const cache = await caches.open(CACHE)
    if (request.mode === 'navigate') {
      try {
        return await fetch(request)
      } catch {
        return (await cache.match('/')) || Response.error()
      }
    }
    return (await cache.match(request)) || fetch(request)
  })())
})

self.addEventListener('notificationclick', event => {
  event.notification.close()
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    if (windows.length) await windows[0].focus()
    else await self.clients.openWindow('/')
  })())
})
