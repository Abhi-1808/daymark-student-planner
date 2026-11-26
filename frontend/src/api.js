export async function api(path, { method = 'GET', payload, file, signal } = {}) {
  const response = await fetch(path, {
    method, credentials: 'same-origin', signal,
    body: file || (payload === undefined ? undefined : JSON.stringify(payload)),
    headers: payload === undefined ? undefined : { 'Content-Type': 'application/json' },
  })
  const result = await response.json().catch(() => null)
  if (!response.ok) {
    const error = new Error(result?.detail || `Daymark returned HTTP ${response.status}.`)
    error.status = response.status
    throw error
  }
  return result
}

function cache(mode, action) {
  if (!globalThis.indexedDB) return Promise.resolve(null)
  return new Promise(resolve => {
    const open = indexedDB.open('daymark-view', 1)
    open.onupgradeneeded = () => open.result.createObjectStore('workspace')
    open.onerror = () => resolve(null)
    open.onsuccess = () => {
      const database = open.result
      const transaction = database.transaction('workspace', mode)
      const request = action(transaction.objectStore('workspace'))
      transaction.oncomplete = () => { database.close(); resolve(request.result ?? null) }
      transaction.onabort = () => { database.close(); resolve(null) }
    }
  })
}
export const readCache = () => cache('readonly', store => store.get('snapshot'))
export const writeCache = (workspace) => cache('readwrite', store => store.put({ workspace, saved: Date.now() }, 'snapshot'))
export const clearCache = () => cache('readwrite', store => store.delete('snapshot'))
