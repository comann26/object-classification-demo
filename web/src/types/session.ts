// The request that started the current session, kept by App as "the active
// session" per docs/design.md §1 ("No remembered inputs" — inputs reset, but
// the active session is shown separately).
export interface ActiveSession {
  threat_objects: string[]
  source: string
  save_stills: boolean
  [k: string]: unknown
}
