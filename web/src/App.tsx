import { useEffect, useReducer, useRef, useState } from 'react'
import { api } from '@/api/client'
import type { Event } from '@/api/types'
import type { ActiveSession } from '@/types/session'
import { ThreatControl } from '@/components/ThreatControl'
import { VideoView } from '@/components/VideoView'
import { StatusBar } from '@/components/StatusBar'
import { EventFeed } from '@/components/EventFeed'
import { EvidencePanel } from '@/components/EvidencePanel'
import { CriticalAlert } from '@/components/CriticalAlert'
import { SettingsDrawer } from '@/components/SettingsDrawer'
import { HistoryDrawer } from '@/components/HistoryDrawer'
import { eventStoreReducer, initialEventStoreState } from '@/lib/eventStore'
import { Button } from '@/components/ui/button'

// Shown when the current session ends on its own (docs/setup-guide.md troubleshooting).
const END_MESSAGES: Record<string, string> = {
  error: 'Something went wrong — click Go to restart',
  camera_lost: 'Camera disconnected — click Go to restart',
  idle: 'Stopped because the page was closed — click Go to restart',
}

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

  useEffect(() => {
    const socket = api.eventsSocket()
    socket.onmessage = (event: { data: string }) => {
      let data: Event
      try {
        data = JSON.parse(event.data)
      } catch {
        return
      }
      dispatch({ type: 'event', event: data })
      // Go and Apply zone stop the old session first, so its session.ended
      // arrives too: only the current session's end clears the page.
      if (data.type === 'session.ended' && data.session_id === sessionIdRef.current) {
        sessionIdRef.current = null
        setActive(null)
        setRestartMessage(END_MESSAGES[String(data.reason)] ?? null)
      }
    }
    return () => socket.close()
  }, [])

  async function applyZone(zone: [number, number][] | null) {
    const previous = sessionIdRef.current
    sessionIdRef.current = null // the replaced session's end is expected; ignore it
    try {
      sessionIdRef.current = (await api.applyZone(zone)).session_id
    } catch (e) {
      // The old session may or may not still run (e.g. "starting" vs a camera error).
      const health = await api.health().catch(() => null)
      if (health?.session_id === previous) sessionIdRef.current = previous
      else setActive(null)
      throw e
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
        onSessionStarted={(session) => {
          sessionIdRef.current = session.session_id
          setActive(session)
          setRestartMessage(null)
          setSessionKey((k) => k + 1)
        }}
        onStopped={() => {
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

      <VideoView key={sessionKey} active={active !== null} onApplyZone={applyZone} />

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
