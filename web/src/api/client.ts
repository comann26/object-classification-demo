import type { Event, SessionRequest, ZoneRequest } from './types'

// Read once at module load, per docs/design.md §4 ("the page reads it from
// its URL and keeps it in memory"). Every route but GET / and static assets
// requires it.
const TOKEN = new URLSearchParams(window.location.search).get('t') ?? ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { ...init?.headers, 'X-Demo-Token': TOKEN },
  })
  if (!res.ok) {
    throw new Error(`${init?.method ?? 'GET'} ${path} failed: ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

interface HealthResponse {
  status: string
  session_id: string | null
  fps: number | null
  camera: string | null
  model: string | null
  input_size: number | null
  device: string | null
}

interface Camera {
  id: string
  name: string
}

export const api = {
  startSession: (req: SessionRequest) => request('/session', jsonInit('POST', req)),
  applyZone: (zone: ZoneRequest['zone']) =>
    request('/session/zone', jsonInit('POST', { zone })),
  stop: () => request('/session', { method: 'DELETE' }),
  quit: () => request('/quit', { method: 'POST' }),
  health: () => request<HealthResponse>('/health'),
  cameras: () => request<Camera[]>('/cameras'),
  getConfig: () => request<Record<string, unknown>>('/config'),
  putConfig: (cfg: Record<string, unknown>) => request('/config', jsonInit('PUT', cfg)),
  sessions: () => request<unknown[]>('/sessions'),
  sessionEvents: (id: string) => request<Event[]>(`/sessions/${id}/events`),
  eventsSocket: (): WebSocket => new WebSocket(`ws://${window.location.host}/events?t=${TOKEN}`),
  videoUrl: (): string => `/video?t=${TOKEN}`,
}
