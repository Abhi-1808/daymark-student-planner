import { createHash } from 'node:crypto'
import { readFile, readdir, writeFile } from 'node:fs/promises'

const output = new URL('./dist/', import.meta.url)
const files = (await readdir(output, { recursive: true, withFileTypes: true }))
  .filter(file => file.isFile()).map(file => `${file.parentPath ?? file.path}/${file.name}`).sort()
const hash = createHash('sha256')
for (const file of files) hash.update(await readFile(file))
const worker = new URL('sw.js', output)
await writeFile(worker, (await readFile(worker, 'utf8')).replace('__DAYMARK_BUILD__', hash.digest('hex').slice(0, 16)))
