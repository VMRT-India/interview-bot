import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// No <StrictMode>: this app's core feature is a stateful WebSocket interview
// session (see useInterviewSocket) — StrictMode's dev-only double-invoke of
// effects opens two real sockets against the same backend session, each
// independently advancing a turn, which duplicates questions and burns real
// LLM calls. Not worth it for the diagnostic value here.
createRoot(document.getElementById('root')!).render(<App />)
