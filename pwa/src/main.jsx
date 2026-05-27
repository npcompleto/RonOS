import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { logger } from './logger'

// Log errori globali non gestiti
window.addEventListener('error', (event) => {
  logger.error(`Uncaught Error: ${event.message} at ${event.filename}:${event.lineno}`);
});

window.addEventListener('unhandledrejection', (event) => {
  logger.error(`Unhandled Rejection: ${event.reason}`);
});

logger.info('PWA started');

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
