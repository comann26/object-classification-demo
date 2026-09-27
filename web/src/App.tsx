import { useEffect, useReducer, useRef, useState } from 'react'
import { api } from '@/api/client'
import type { Event, SessionEnded } from '@/api/types'
import type { ActiveSession } from '@/types/session'
import { ThreatControl } from '@/components/ThreatControl'
import { VideoView } from '@/components/VideoView'
import { StatusBar } from '@/components/StatusBar'
import { EventFeed } from '@/components/EventFeed'
import { EvidencePanel } from '@/components/EvidencePanel'
import { CriticalAlert } from '@/components/CriticalAlert'
import { SettingsDrawer } from '@/components/SettingsDrawer'
import { HistoryDrawer } from '@/components/HistoryDrawer'
import { eventStoreReducer, findSessionEnded, initialEventStoreState } from '@/lib/eventStore'
import { Button } from '@/components/ui/button'

// Shown when the current session ends on its own (docs/setup-guide.md troubleshooting).
const END_MESSAGES: Record<string, string> = {
  error: 'Something went wrong — click Go to restart',
  camera_lost: 'Camera disconnected — click Go to restart',
  idle: 'Stopped because the page was closed — click Go to restart',
}

const STARTING_TIMEOUT_MS = 90_000
const HEALTH_POLL_MS = 500
const STARTING_MESSAGE =
  'Starting the camera and loading the model — the first start can take up to a minute.'
const STARTING_TIMEOUT_MESSAGE = 'Still starting — check the black console window for messages.'
const APPLYING_ZONE_MESSAGE = 'Applying the new zone…'

function App() {
  const [active, setActive] = useState<ActiveSession | null>(null)
  // Read inside the WebSocket handler, which is bound once, hence a ref.
  const sessionIdRef = useRef<string | null>(null)
  // Remounts VideoView on Go/Stop so its polygon resets, per design.md §1
  // ("the drawn zone stays visible until the next Go or Stop").
  const [sessionKey, setSessionKey] = useState(0)
  const [closed, setClosed] = useState(false)
  const [restartMessage, setRestartMessage] = useState<string | null>(null)
  const [store, dispatch] = useReducer(eventStoreReducer, initialEventStoreState)
  const [selectedTrackId, setSelectedTrackId] = useState<number | null>(null)
  // Mirrors `store`, updated synchronously (not via effect) so it's never
  // stale inside a POST /session(/zone) response handler that was bound
  // before a session.ended arrived over the socket in the meantime.
  const storeRef = useRef(initialEventStoreState)

  // True from the moment Go is clicked until the first video frame shows (or
  // health reports fps>0 for the new session) — whichever comes first.
  const [starting, setStarting] = useState(false)
  const [startingTimedOut, setStartingTimedOut] = useState(false)
  // Short-lived version of the same overlay while Apply zone is in flight.
  const [applyingZone, setApplyingZone] = useState(false)
  const startingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const healthPollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  function clearStarting() {
    setStarting(false)
    setStartingTimedOut(false)
    if (startingTimeoutRef.current) clearTimeout(startingTimeoutRef.current)
    startingTimeoutRef.current = null
    if (healthPollRef.current) clearInterval(healthPollRef.current)
    healthPollRef.current = null
  }

  // Unmount safety net for the timers above.
  useEffect(() => clearStarting, [])

  function onStartBegin() {
    setStarting(true)
    setStartingTimedOut(false)
    setRestartMessage(null)
    startingTimeoutRef.current = setTimeout(() => setStartingTimedOut(true), STARTING_TIMEOUT_MS)
  }

  // Polls /health until it reports the new session running with fps>0 — the
  // other "loader done" signal besides the video <img> load event.
  function startHealthPoll(newSessionId: string) {
    healthPollRef.current = setInterval(() => {
      api
        .health()
        .then((health) => {
          if (health.session_id === newSessionId && health.status === 'running' && (health.fps ?? 0) > 0) {
            clearStarting()
          }
        })
        .catch(() => {}) // transient errors while starting are expected; keep polling
    }, HEALTH_POLL_MS)
  }

  function endSession(ended: SessionEnded) {
    clearStarting()
    sessionIdRef.current = null
    setActive(null)
    setRestartMessage(END_MESSAGES[String(ended.reason)] ?? null)
  }

  // The server can start — and kill — a session before its HTTP response is
  // sent, so the session.ended may already be in the feed by the time the
  // page adopts the id. Returns it so the caller can end the same way a
  // live matching session.ended would.
  function alreadyEnded(sessionId: string): SessionEnded | undefined {
    return findSessionEnded(storeRef.current.feed, sessionId)
  }

  useEffect(() => {
    const socket = api.eventsSocket()
    socket.onmessage = (event: { data: string }) => {
      let data: Event
      try {
        data = JSON.parse(event.data)
      } catch {
        return
      }
      storeRef.current = eventStoreReducer(storeRef.current, { type: 'event', event: data })
      dispatch({ type: 'event', event: data })
      // Go and Apply zone stop the old session first, so its session.ended
      // arrives too: only the current session's end clears the page.
      if (data.type === 'session.ended' && data.session_id === sessionIdRef.current) {
        endSession(data)
      }
    }
    return () => socket.close()
  }, [])

  async function applyZone(zone: [number, number][] | null) {
    const previous = sessionIdRef.current
    sessionIdRef.current = null // the replaced session's end is expected; ignore it
    setApplyingZone(true)
    try {
      const { session_id } = await api.applyZone(zone)
      const ended = alreadyEnded(session_id)
      if (ended) endSession(ended)
      else sessionIdRef.current = session_id
    } catch (e) {
      // The old session may or may not still run (e.g. "starting" vs a camera error).
      const health = await api.health().catch(() => null)
      if (health?.session_id === previous) sessionIdRef.current = previous
      else setActive(null)
      throw e
    } finally {
      setApplyingZone(false)
    }
  }

  if (closed) {
    return (
      <div className="flex min-h-svh items-center justify-center bg-background text-foreground">
        <p className="font-heading text-xl">Demo closed — you can close this tab</p>
      </div>
    )
  }

  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="flex items-center justify-between border-b border-border px-6 py-4">
        <h1 className="font-heading text-2xl font-semibold tracking-wide">
          Object Classification Demo
        </h1>
        <div className="flex gap-2">
          <HistoryDrawer dispatch={dispatch} />
          <SettingsDrawer />
        </div>
      </header>

      <ThreatControl
        active={active}
        starting={starting}
        startingTimedOut={startingTimedOut}
        onStartBegin={onStartBegin}
        onSessionStarted={(session) => {
          const ended = alreadyEnded(session.session_id)
          if (ended) {
            endSession(ended)
            return
          }
          sessionIdRef.current = session.session_id
          setActive(session)
          setRestartMessage(null)
          setSessionKey((k) => k + 1)
          startHealthPoll(session.session_id)
        }}
        onStartFailed={clearStarting}
        onStopped={() => {
          clearStarting()
          sessionIdRef.current = null
          setActive(null)
          setSessionKey((k) => k + 1)
        }}
        onQuit={() => setClosed(true)}
      />

      {restartMessage && <p className="px-6 py-2 text-sm text-destructive">{restartMessage}</p>}

      {store.replay && (
        <div className="flex items-center justify-between bg-muted px-6 py-2 text-sm">
          <span>Replaying a past session</span>
          <Button variant="outline" size="sm" onClick={() => dispatch({ type: 'replay_end' })}>
            Back to live
          </Button>
        </div>
      )}

      <CriticalAlert tracks={store.tracks} replay={store.replay} />

      <VideoView
        key={sessionKey}
        active={active !== null}
        onApplyZone={applyZone}
        starting={starting}
        onFirstFrame={clearStarting}
        overlayMessage={
          starting
            ? startingTimedOut
              ? STARTING_TIMEOUT_MESSAGE
              : STARTING_MESSAGE
            : applyingZone
              ? APPLYING_ZONE_MESSAGE
              : null
        }
      />

      <div className="grid grid-cols-1 gap-0 border-t border-border md:grid-cols-2">
        <EventFeed
          feed={store.feed}
          selectedTrackId={selectedTrackId}
          onSelectTrack={setSelectedTrackId}
        />
        <EvidencePanel track={selectedTrackId !== null ? (store.tracks[selectedTrackId] ?? null) : null} />
      </div>

      <StatusBar sourceHealth={store.latestHealth ?? null} />
    </div>
  )
}

export default App
