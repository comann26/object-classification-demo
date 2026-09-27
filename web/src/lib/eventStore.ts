import type { Event, SessionEnded, SourceHealth, TrackUpdated } from '@/api/types'

// Pure reducer over the event stream (no React), per task-19-brief.md.
// App owns the single WebSocket and drives this with useReducer.
const FEED_LIMIT = 500

export interface EventStoreState {
  tracks: Record<number, TrackUpdated>
  feed: Event[]
  sessionEnded?: SessionEnded
  latestHealth?: SourceHealth
  replay: boolean
}

export const initialEventStoreState: EventStoreState = {
  tracks: {},
  feed: [],
  replay: false,
}

export type EventStoreAction =
  | { type: 'event'; event: Event }
  | { type: 'replay_start'; events: Event[] }
  | { type: 'replay_end' }

function pushFeed(feed: Event[], event: Event): Event[] {
  const next = feed.length >= FEED_LIMIT ? feed.slice(feed.length - FEED_LIMIT + 1) : feed
  return [...next, event]
}

// Applies one event regardless of replay mode; used both for live events and
// to fold a replayed history into a fresh state.
function applyEvent(state: EventStoreState, event: Event): EventStoreState {
  if (event.type === 'session.started') {
    // Go never carries anything over (design.md §1).
    return { tracks: {}, feed: pushFeed([], event), replay: state.replay }
  }

  const feed = pushFeed(state.feed, event)
  switch (event.type) {
    case 'track.updated':
      return {
        ...state,
        feed,
        tracks: { ...state.tracks, [event.track.track_id]: event },
      }
    case 'track.ended': {
      const tracks = { ...state.tracks }
      delete tracks[event.track_id]
      return { ...state, feed, tracks }
    }
    case 'source.health':
      return { ...state, feed, latestHealth: event }
    case 'session.ended':
      return { ...state, feed, sessionEnded: event }
    default:
      return { ...state, feed }
  }
}

// Looks up an already-received session.ended for sessionId, most recent
// first. Used by App to honour one that arrived before the HTTP response
// that hands it the session id (App §"adoptSession").
export function findSessionEnded(feed: Event[], sessionId: string): SessionEnded | undefined {
  for (let i = feed.length - 1; i >= 0; i--) {
    const event = feed[i]
    if (event.type === 'session.ended' && event.session_id === sessionId) return event
  }
  return undefined
}

export function eventStoreReducer(
  state: EventStoreState,
  action: EventStoreAction,
): EventStoreState {
  switch (action.type) {
    case 'event':
      // ponytail: live events are simply dropped while replaying (no queue
      // to resume from); upgrade to a buffer if "resume live mid-replay"
      // ever needs to preserve what arrived during playback.
      if (state.replay) return state
      return applyEvent(state, action.event)
    case 'replay_start': {
      let next: EventStoreState = { tracks: {}, feed: [], replay: true }
      for (const event of action.events) next = applyEvent(next, event)
      return { ...next, replay: true }
    }
    case 'replay_end':
      return { ...initialEventStoreState, replay: false }
    default:
      return state
  }
}
