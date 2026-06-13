// Native WebSocket client for Django Channels (replaces laravel-echo/pusher).
// Single connection to /ws/crm; emits 'lead.updated' and 'notification' events.

let socket = null
let currentToken = null
const listeners = { 'lead.updated': new Set(), notification: new Set() }
let reconnectTimer = null

function wsUrl(token) {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host = import.meta.env.VITE_WS_HOST || `${window.location.hostname}:8000`
  return `${proto}://${host}/ws/crm?token=${encodeURIComponent(token)}`
}

function open() {
  if (!currentToken) return
  socket = new WebSocket(wsUrl(currentToken))

  socket.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data)
      const set = listeners[msg.event]
      if (set) set.forEach((cb) => cb(msg))
    } catch {
      /* ignore malformed frames */
    }
  }

  socket.onclose = () => {
    socket = null
    if (currentToken) {
      clearTimeout(reconnectTimer)
      reconnectTimer = setTimeout(open, 3000) // auto-reconnect
    }
  }
}

export function connectEcho(token) {
  currentToken = token
  if (!socket) open()
  return realtime
}

export function disconnectEcho() {
  currentToken = null
  clearTimeout(reconnectTimer)
  if (socket) {
    socket.close()
    socket = null
  }
}

// Small event-emitter API used by components.
export const realtime = {
  on(event, cb) {
    listeners[event]?.add(cb)
    return () => listeners[event]?.delete(cb)
  },
}
