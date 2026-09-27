// Maps a client-space click on an <img> (rendered with object-fit: contain)
// to normalized [0..1] frame coordinates, accounting for the letterbox bars
// contain adds on one axis. Returns null when the click lands in a bar.
export function clientToFrame(
  x: number,
  y: number,
  box: DOMRect,
  frameW: number,
  frameH: number,
): [number, number] | null {
  const boxAspect = box.width / box.height
  const frameAspect = frameW / frameH

  let contentW: number
  let contentH: number
  if (frameAspect > boxAspect) {
    // Frame is relatively wider than the box: full width, letterboxed top/bottom.
    contentW = box.width
    contentH = box.width / frameAspect
  } else {
    // Frame is relatively taller than the box: full height, letterboxed left/right.
    contentH = box.height
    contentW = box.height * frameAspect
  }
  const offsetX = (box.width - contentW) / 2
  const offsetY = (box.height - contentH) / 2

  const localX = x - box.left - offsetX
  const localY = y - box.top - offsetY

  if (localX < 0 || localX > contentW || localY < 0 || localY > contentH) {
    return null
  }

  return [localX / contentW, localY / contentH]
}
