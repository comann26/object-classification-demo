# Object Classification Demo

A self-contained demo: a live webcam feed goes in, and each object comes out **detected, classified and tracked** (for example, its direction of motion), with two separate scores:

- **Threat score:** how concerning the object's behavior is. It is advisory only.
- **Confidence score:** how much to trust the observation.

## What this repo is, and what it isn't

This repo is **technical proof**: can we detect, track and score objects from a camera, with clean code that could later become an API or be embedded in a larger system?

**Product documentation don't live here.** Decisions or Documentation such as which signals *should* count as a threat, how the output feeds Guardian Intelligence, and what's off-limits for civil-liberty reasons belong to [`scrye-docs`](../scrye-docs):

| Question | Where it's answered |
|---|---|
| What is Guardian Intelligence and what data does it expect? | `scrye-docs/products/guardian-intelligence.md` |
| Which signals drive the threat score, and why? | `scrye-docs/decisions/2026-09-26-camera-threat-scoring.md` |
| How does this demo implement those decisions? | This repo |

When a product decision changes, update `scrye-docs` first, then change code here to match. This repo's docs link to those decisions; they don't restate them.

## Status

Design phase. There is no code yet. See [docs/requirements.md](docs/requirements.md).

**Setup goal:** a non-technical person can install and run the demo with a download and a double-click. They don't need a terminal or to install Python themselves.
