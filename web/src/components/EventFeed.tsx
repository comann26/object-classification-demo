import type { Event } from '@/api/types'
import { BAND_COLOR_CLASS, BAND_LABEL } from '@/lib/band'

interface EventFeedProps {
  feed: Event[]
  selectedTrackId: number | null
  onSelectTrack: (trackId: number) => void
}

function summarize(event: Event): { text: string; trackId: number | null } {
  switch (event.type) {
    case 'track.updated':
      return {
        text: `Track ${event.track.track_id} (${event.track.class}) — ${BAND_LABEL[event.threat.band]}`,
        trackId: event.track.track_id,
      }
    case 'track.ended':
      return { text: `Track ${event.track_id} ended — peak ${BAND_LABEL[event.peak_band]}`, trackId: null }
    case 'session.started':
      return { text: 'Session started', trackId: null }
    case 'session.ended':
      return { text: `Session ended (${event.reason})`, trackId: null }
    case 'source.health':
      return { text: `${event.code}: ${event.detail}`, trackId: null }
    case 'pipeline.changed':
      return { text: `Pipeline changed: ${event.reason}`, trackId: null }
    default:
      return { text: (event as Event).type ?? 'event', trackId: null }
  }
}

// The live/replayed event log — clicking a track.updated row selects that
// track for the EvidencePanel (task-19-brief.md).
export function EventFeed({ feed, selectedTrackId, onSelectTrack }: EventFeedProps) {
  return (
    <ul className="flex flex-col-reverse gap-1 overflow-y-auto p-2 text-sm" data-testid="event-feed">
      {feed.map((event, i) => {
        const { text, trackId } = summarize(event)
        const band = event.type === 'track.updated' ? event.threat.band : null
        const selected = trackId !== null && trackId === selectedTrackId
        return (
          <li key={`${event.event_id}-${i}`}>
            <button
              type="button"
              disabled={trackId === null}
              onClick={() => trackId !== null && onSelectTrack(trackId)}
              className={`w-full rounded px-2 py-1 text-left ${
                selected ? 'bg-muted' : 'hover:bg-muted/50'
              } ${trackId === null ? 'cursor-default text-muted-foreground' : ''} ${
                band ? BAND_COLOR_CLASS[band] : ''
              }`}
            >
              {text}
            </button>
          </li>
        )
      })}
    </ul>
  )
}
