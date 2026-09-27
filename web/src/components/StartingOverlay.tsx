import { Loader2 } from 'lucide-react'

interface StartingOverlayProps {
  message: string
}

// Centred overlay shown over the video area from Go until the first frame,
// and briefly again while an Apply zone request is in flight.
export function StartingOverlay({ message }: StartingOverlayProps) {
  return (
    <div className="absolute inset-0 flex items-center justify-center gap-2 bg-background/80 p-4 text-center text-sm">
      <Loader2 className="size-5 shrink-0 animate-spin" />
      <span>{message}</span>
    </div>
  )
}
