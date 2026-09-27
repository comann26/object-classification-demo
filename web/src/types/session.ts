// The request that started the current session, kept by App as "the active
// session" per docs/design.md §1 ("No remembered inputs" — inputs reset, but
// the active session is shown separately).
export interface ActiveSession {
  threat_objects: string[]
  source: string
  save_stills: boolean
  [k: string]: unknown
}

// One row of GET /sessions, newest first (plan Task 12 fixes this shape as
// `[{session_id, started_at, threat_objects, peak_band, ended_normally}]`).
// No generated schema for this yet — the route isn't implemented on this
// branch — so this is hand-typed and awaits the real contract at merge.
export interface SessionSummary {
  session_id: string
  started_at: string
  threat_objects: string[]
  peak_band: 'low' | 'medium' | 'high' | 'critical'
  ended_normally: boolean
  [k: string]: unknown
}
