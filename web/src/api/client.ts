import type { Event, ScoringConfig, SessionRequest, ZoneRequest } from './types'
import type { SessionSummary } from '@/types/session'

// Read once at module load, per docs/design.md §4 ("the page reads it from
// its URL and keeps it in memory"). Every route but GET / and static assets
// requires it.
const TOKEN = new URLSearchParams(window.location.search).get('t') ?? ''

// Thrown on a non-2xx response. When the server sent a JSON {code, message}
// body (docs/design.md §4), `message` is that text verbatim; otherwise it
// falls back to a generic description.
export class ApiError extends Error {
  code?: string
  constructor(message: string, code?: string) {
    super(message)
    this.code = code
  }
}

interface ErrorBody {
  code?: string
  message?: string
  detail?: string | { msg?: string }[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { ...init?.headers, 'X-Demo-Token': TOKEN },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => undefined as ErrorBody | undefined)
    // FastAPI's own errors (422 validation, HTTPException) send `detail`, not `message`.
    const detail = typeof body?.detail === 'string' ? body.detail : body?.detail?.[0]?.msg
    throw new ApiError(
      body?.message ?? detail ?? `${init?.method ?? 'GET'} ${path} failed: ${res.status}`,
      body?.code,
    )
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

export interface HealthResponse {
  status: string
  session_id: string | null
  fps: number | null
  camera: string | null
  model: string | null
  input_size: number | null
  device: string | null
}

export interface SessionStarted {
  session_id: string
}

export interface Camera {
  id: string
  name: string
}

export const api = {
  startSession: (req: SessionRequest) => request<SessionStarted>('/session', jsonInit('POST', req)),
  // Apply/clear zone restarts the session, so it answers with the new session_id.
  applyZone: (zone: ZoneRequest['zone']) =>
    request<SessionStarted>('/session/zone', jsonInit('POST', { zone })),
  stop: () => request('/session', { method: 'DELETE' }),
  quit: () => request('/quit', { method: 'POST' }),
  health: () => request<HealthResponse>('/health'),
  cameras: () => request<Camera[]>('/cameras'),
  getConfig: () => request<ScoringConfig>('/config'),
  putConfig: (cfg: ScoringConfig) => request<void>('/config', jsonInit('PUT', cfg)),
  sessions: () => request<SessionSummary[]>('/sessions'),
  sessionEvents: (id: string) => request<Event[]>(`/sessions/${id}/events`),
  eventsSocket: (): WebSocket => new WebSocket(`ws://${window.location.host}/events?t=${TOKEN}`),
  // `s=<sessionId>` busts the browser's image cache: an identical URL across
  // sessions can otherwise be served from the "list of available images"
  // instead of re-requested, showing a stale (or the pre-session empty) feed.
  videoUrl: (sessionId: string): string => `/video?t=${TOKEN}&s=${encodeURIComponent(sessionId)}`,
}
