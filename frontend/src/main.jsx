import { createRoot } from 'react-dom/client'
import { App } from './app.jsx'
import { applyTheme, colorMode } from './device.js'
import '@fontsource/carlito/latin-400.css'
import '@fontsource/carlito/latin-700.css'
import './styles.css'

applyTheme(colorMode())
createRoot(document.getElementById('root')).render(<App />)
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}))
}
