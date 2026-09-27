import { useEffect, useRef, useState } from 'react'
import type { TrackUpdated } from '@/api/types'
import type { Band } from '@/lib/band'
import { Button } from '@/components/ui/button'

const MUTE_KEY = 'criticalAlertMuted'

function readMuted(): boolean {
  try {
    return localStorage.getItem(MUTE_KEY) === 'true'
  } catch {
    return false
  }
}

function writeMuted(muted: boolean): void {
  try {
    localStorage.setItem(MUTE_KEY, String(muted))
  } catch {
    // ignore — localStorage may be unavailable (private mode, disabled cookies)
  }
}

// 880 Hz for 200 ms, once, via the Web Audio API. Tests mock AudioContext.
function playTone(): void {
  const ctx = new AudioContext()
  const osc = ctx.createOscillator()
  osc.type = 'sine'
  osc.frequency.value = 880
  osc.connect(ctx.destination)
  osc.start()
  osc.stop(ctx.currentTime + 0.2)
  osc.onended = () => ctx.close()
}

interface CriticalAlertProps {
  tracks: Record<number, TrackUpdated>
  // History replay folds a whole session into `tracks` in one dispatch —
  // that is not a live entry into critical, so tones and the banner are
  // suppressed while true (Fix round 1, Important 2).
  replay: boolean
}

// Red banner + tone on entry into critical, per track. task-19-brief.md:
// critical→high→critical plays 2 tones; held critical plays 1.
export function CriticalAlert({ tracks, replay }: CriticalAlertProps) {
  const [muted, setMuted] = useState(readMuted)
  const prevBands = useRef<Record<number, Band>>({})
  const wasReplaying = useRef(replay)

  useEffect(() => writeMuted(muted), [muted])

  useEffect(() => {
    // Returning to live loses all continuity with whatever replay showed
    // (the store resets `tracks` to {} on replay_end too), so forget every
    // remembered band: the next live snapshot is a fresh baseline, not a
    // continuation of the replayed one.
    if (wasReplaying.current && !replay) {
      prevBands.current = {}
    }
    wasReplaying.current = replay
  }, [replay])

  useEffect(() => {
    if (replay) return
    for (const [idStr, track] of Object.entries(tracks)) {
      const id = Number(idStr)
      const band = track.threat.band
      const prev = prevBands.current[id]
      if (band === 'critical' && prev !== 'critical' && !muted) {
        playTone()
      }
      prevBands.current[id] = band
    }
    const activeIds = new Set(Object.keys(tracks).map(Number))
    for (const id of Object.keys(prevBands.current).map(Number)) {
      if (!activeIds.has(id)) delete prevBands.current[id]
    }
  }, [tracks, muted, replay])

  const criticalTracks = replay
    ? []
    : Object.values(tracks).filter((t) => t.threat.band === 'critical')

  return (
    <div>
      {criticalTracks.length > 0 && (
        <div
          role="alert"
          className="flex items-center justify-between bg-destructive px-4 py-2 text-sm font-medium text-white"
        >
          <span>
            Critical: {criticalTracks.length} track{criticalTracks.length > 1 ? 's' : ''}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setMuted((m) => !m)}
            className="border-white text-white"
          >
            {muted ? 'Unmute' : 'Mute'}
          </Button>
        </div>
      )}
    </div>
  )
}
