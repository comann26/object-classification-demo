import { useState } from 'react'
import { api } from '@/api/client'
import type { EventStoreAction } from '@/lib/eventStore'
import type { SessionSummary } from '@/types/session'
import { BAND_LABEL } from '@/lib/band'
import { Button } from '@/components/ui/button'
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from '@/components/ui/drawer'

interface HistoryDrawerProps {
  dispatch: (action: EventStoreAction) => void
}

function errorMessage(e: unknown, fallback: string): string {
  return e instanceof Error ? e.message : fallback
}

// Lists past sessions (GET /sessions); opening one replays its events into
// the store — task-19-brief.md's HistoryDrawer.
export function HistoryDrawer({ dispatch }: HistoryDrawerProps) {
  const [open, setOpen] = useState(false)
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  function handleOpenChange(next: boolean) {
    setOpen(next)
    if (next && !sessions) {
      api
        .sessions()
        .then(setSessions)
        .catch((e) => setError(errorMessage(e, 'Failed to load session history.')))
    }
  }

  async function replaySession(sessionId: string) {
    setError(null)
    try {
      const events = await api.sessionEvents(sessionId)
      dispatch({ type: 'replay_start', events })
      setOpen(false)
    } catch (e) {
      setError(errorMessage(e, 'Failed to load that session.'))
    }
  }

  return (
    <Drawer open={open} onOpenChange={handleOpenChange} direction="right">
      <DrawerTrigger asChild>
        <Button variant="outline">History</Button>
      </DrawerTrigger>
      <DrawerContent>
        <DrawerHeader>
          <DrawerTitle>Session history</DrawerTitle>
        </DrawerHeader>

        <div className="flex flex-col gap-2 overflow-y-auto p-4">
          {error && <p className="text-sm text-destructive">{error}</p>}
          {!sessions && !error && <p className="text-sm text-muted-foreground">Loading…</p>}
          {sessions?.length === 0 && (
            <p className="text-sm text-muted-foreground">No past sessions.</p>
          )}
          {sessions?.map((s) => (
            <button
              key={s.session_id}
              type="button"
              onClick={() => replaySession(s.session_id)}
              className="flex flex-col items-start gap-0.5 rounded-md border border-border p-2 text-left text-sm hover:bg-muted"
            >
              <span>{s.started_at}</span>
              <span className="text-muted-foreground">{s.threat_objects.join(', ')}</span>
              <span>
                Peak: {BAND_LABEL[s.peak_band]} — {s.truncated ? 'truncated' : 'ended normally'}
              </span>
            </button>
          ))}
        </div>
      </DrawerContent>
    </Drawer>
  )
}
