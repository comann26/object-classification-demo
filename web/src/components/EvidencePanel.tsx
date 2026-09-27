import type { TrackUpdated } from '@/api/types'
import { BAND_COLOR_CLASS, BAND_LABEL } from '@/lib/band'
import { Badge } from '@/components/ui/badge'

interface EvidencePanelProps {
  track: TrackUpdated | null
}

// The selected track's summary, evidence table, confidence and unknowns —
// task-19-brief.md's EvidencePanel interface.
export function EvidencePanel({ track }: EvidencePanelProps) {
  if (!track) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        Select a track from the event feed to see its evidence.
      </div>
    )
  }

  const { threat, confidence, unknowns, summary } = track

  return (
    <div className="flex flex-col gap-3 border-t border-border p-4">
      <div className="flex items-center gap-2">
        <span className={`font-heading text-lg font-semibold ${BAND_COLOR_CLASS[threat.band]}`}>
          {BAND_LABEL[threat.band]}
        </span>
        <span className="text-sm text-muted-foreground">score {threat.score}</span>
      </div>

      <p className="text-sm">{summary}</p>

      <table className="w-full text-left text-sm">
        <thead className="text-muted-foreground">
          <tr>
            <th className="pr-2 font-normal">Evidence</th>
            <th className="pr-2 font-normal">Contribution</th>
            <th className="font-normal">Type</th>
          </tr>
        </thead>
        <tbody>
          {threat.evidence.map((item, i) => (
            <tr key={i}>
              <td className="pr-2">{item.text}</td>
              <td className="pr-2">
                {item.contribution > 0 ? `+${item.contribution}` : item.contribution}
              </td>
              <td>
                <Badge variant={item.type === 'supporting' ? 'default' : 'outline'}>
                  {item.type}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div>
        <div className="text-sm font-medium">Confidence: {confidence.score}</div>
        <div className="flex flex-wrap gap-x-4 text-xs text-muted-foreground">
          <span>Detector: {confidence.dimensions.detector}</span>
          <span>Track stability: {confidence.dimensions.track_stability}</span>
          <span>Image quality: {confidence.dimensions.image_quality}</span>
        </div>
      </div>

      {unknowns.length > 0 && (
        <div>
          <div className="text-sm font-medium">Unknowns</div>
          <ul className="text-xs text-muted-foreground">
            {unknowns.map((u, i) => (
              <li key={i}>
                {u.code}: {u.detail}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
