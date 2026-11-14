import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { captureDemoToken } from './lib/api'
import { installAudioUnlock } from './lib/sound'
import './index.css'

// `?demo=TOKEN` is read once and kept in localStorage (CONTRACT §8.5); audio waits for the first tap.
captureDemoToken()
installAudioUnlock()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
