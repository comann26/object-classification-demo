---
title: Knowledge notes
status: living
date: 2026-09-27
related:
  - ../design.md
  - ../build-log.md
---

# Knowledge notes

One file per learning: something measured or discovered while building or running the demo,
that later work would otherwise have to rediscover. Technical learnings live here; product
learnings (what should count as a threat, Guardian integration, civil-liberty limits) go in
`../../../scrye-docs` instead.

## Filename

`YYYY-MM-DD-<topic>.md` — the date the fact was established, not when the file was edited.

## Template

Every note has three parts. Keep them short; link to the evidence rather than pasting it.

```markdown
---
title: <one line>
date: YYYY-MM-DD
tags: [topic, topic]
status: measured | verified | TBD
---

# <title>

## Observed
What was found, as a fact (a number, a behavior, a constraint) — not an opinion.

## Evidence
Exactly how it was produced: command, machine, versions, what was held constant. Enough
for someone else to reproduce or refute it.

## Implication
What this means for the code, the docs, or a later task. If it changes a number or a
claim elsewhere (design.md, the setup guide), say where.
```

## Existing notes

| Note | What it's about |
|---|---|
| [2026-09-27-yolo-world-offline.md](2026-09-27-yolo-world-offline.md) | how YOLO-World is kept fully offline after first setup (CLIP weights, Ultralytics settings dir, `YOLO_OFFLINE`) |
| [2026-09-27-fps-dev-windows-cpu.md](2026-09-27-fps-dev-windows-cpu.md) | detector-only fps on the dev Windows laptop, CPU, small model |
| [2026-09-27-fps-dev-windows-nvidia-4070.md](2026-09-27-fps-dev-windows-nvidia-4070.md) | detector-only fps on the dev Windows laptop, RTX 4070 Laptop GPU, small and large models |

## Still TODO (tracked in `../release-checklist.md`)

- Acceptance check results (8/10 links, ≤2/10 false links) per machine type.
- The camera-index-order verification on real machines (design.md §4, Task 11 note).
- fps on Apple Silicon, Intel Mac, and Windows CPU end-to-end (with camera, not detector-only).
- Whether the Mac launcher runs at all — it has not been run on a real Mac yet.
