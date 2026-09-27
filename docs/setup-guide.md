---
title: Setup guide
status: living — screenshots are TODO (see docs/release-checklist.md)
date: 2026-09-27
related:
  - ../README.md
  - release-checklist.md
  - design.md
---

# Setup guide

This is for anyone installing and running the demo — no technical background needed. You will
not use a terminal or install Python yourself.

**What you need:** a Windows or Mac laptop with a webcam, and an internet connection for the
first run only. After that, it works with no internet.

**Minimum computer:** Windows (any), or a Mac on **macOS 14 (Sonoma) or later** if it's an Apple
Silicon Mac (M1/M2/M3/…), or **macOS 12 (Monterey) or later** if it's an older Intel Mac. *(To
be double-checked on real machines — see the release checklist.)*

**Download size on first run:** about **1 GB** on a Mac or a Windows computer without an NVIDIA
graphics card, and about **4.7 GB** on Windows with an NVIDIA graphics card (it downloads a
larger, GPU-accelerated version of the software).

## Windows

1. Download the zip file and **extract it** — right-click it and choose "Extract All…", then
   open the folder that appears. Do not try to run the demo from inside the zip; it will refuse
   with a message telling you to extract it first.

   ![TODO screenshot: extracting the zip in File Explorer](images/todo-win-extract.png)

2. Double-click **`Start Demo.bat`**.

3. Windows will likely show a blue "Windows protected your PC" screen (SmartScreen). Click
   **More info**, then click **Run anyway**.

   ![TODO screenshot: SmartScreen "More info"](images/todo-smartscreen-more-info.png)
   ![TODO screenshot: SmartScreen "Run anyway" button](images/todo-smartscreen-run-anyway.png)

4. A black window (the "console") opens and does some one-time setup — this needs internet and
   can take several minutes the first time. Leave it open. Later runs are much faster and work
   without internet.

5. When it's ready, your web browser opens the demo page by itself.

6. The first time you click **Go**, Windows may ask whether apps can use your camera, or may
   silently block it. If nothing shows in the video, check: **Settings → Privacy & security →
   Camera → "Let desktop apps access your camera"** is turned on.

   ![TODO screenshot: Windows camera privacy setting](images/todo-win-camera-privacy.png)

## Mac

1. Download the zip file and **extract it** — double-click it in Finder, then open the folder
   that appears. Do not run the demo from inside the zip or straight from the Downloads
   "quarantine" view; extract it to a normal folder first.

   ![TODO screenshot: extracting the zip in Finder](images/todo-mac-extract.png)

2. Double-click **`Start Demo.command`**.

3. macOS will likely warn that the file is from an unidentified developer. On **macOS Sequoia
   (15) and later**: go to **System Settings → Privacy & Security**, scroll down, and click
   **Open Anyway** next to the message about `Start Demo.command`. Then double-click it again
   and confirm.

   ![TODO screenshot: Sequoia Privacy & Security "Open Anyway"](images/todo-mac-open-anyway.png)

4. A Terminal window opens and does some one-time setup — this needs internet and can take
   several minutes the first time. Leave it open. Later runs are much faster and work without
   internet.

5. The first time it needs your camera, macOS asks for permission. The prompt names
   **Terminal** (because that's the app actually opening the camera) — click **OK**/**Allow**.

   ![TODO screenshot: macOS camera permission prompt for Terminal](images/todo-mac-camera-permission.png)

   If you accidentally clicked **Don't Allow**, or the video stays black: **System Settings →
   Privacy & Security → Camera → turn on Terminal**, then quit and reopen the demo.

6. When it's ready, your web browser opens the demo page by itself.

> **Note (untested):** the Mac launcher has not yet been run on a real Mac. If any of the steps
> above don't match what you see, please note the difference — see `docs/release-checklist.md`.

## Using it

Once the page is open: type a word for what to look for (for example "knife" or "gun"), pick
your camera if you have more than one, and click **Go**. Click **Stop** to end, or **Quit** to
close the demo entirely.

### Safety note for testing with a real knife

If you're testing with an actual kitchen knife (rather than a toy or replica), handle it the
same way you would in a kitchen: point the blade down and away from yourself and others, don't
wave it around, and put it down between tests. A toy or orange-tipped replica is safer for
repeated testing and works just as well for the demo.

## Updating to a new version

Each new version is a new zip. Extract it to a new folder — don't overwrite the old one while
it still has data you want to keep. To carry your history and any custom settings across:

- Copy the **`logs`** folder from the old install into the new one (this also carries across
  any saved "stills" — snapshot images from past sessions).
- Copy **`config/scoring.json`** from the old install into the new one, if you changed any of
  the sliders and want to keep those settings.

The new version will re-download its setup files on first run, the same as the very first
install.

## Speed (frames per second)

These are detector-only measurements (no camera, no tracking/scoring/drawing) taken on one
development laptop, at three different input sizes. They give a rough sense of relative speed,
not what you'll see end to end — the live demo also does camera capture, tracking, linking,
scoring and drawing, so its fps will be somewhat lower. The demo automatically steps down to a
smaller/faster setup if it measures below about 10 fps for a few seconds.

| Machine | Model | 640 px | 480 px | 320 px |
|---|---|---:|---:|---:|
| Windows laptop, Intel Core i7-13620H, CPU only | small | 11.6 fps | 18.0 fps | 30.5 fps |
| Windows laptop, NVIDIA RTX 4070 Laptop GPU | large | 51.7 fps | 73.4 fps | 76.0 fps |
| Windows laptop, NVIDIA RTX 4070 Laptop GPU | small | 91.3 fps | 101.4 fps | 96.6 fps |
| Apple Silicon Mac | — | TBD (release checklist) | — | — |
| Intel Mac | — | TBD (release checklist) | — | — |
| Windows laptop, CPU only (other hardware) | — | TBD (release checklist) | — | — |

See `docs/knowledge/` for how these were measured.

## Troubleshooting

Find the message you saw on screen (or in the black/Terminal window) in the left column.

| Message you see | What it means | What to do |
|---|---|---|
| "Extract the zip first, then open the extracted folder." | You ran the launcher from inside the zip, or from a temporary folder Windows/macOS made for you. | Extract the whole zip to a normal folder, then double-click the launcher from there. |
| "This download looks incomplete: bin\uv.version is missing. Download the demo again." (Windows) | A file the download depends on is missing — the zip likely didn't download or extract completely. | Delete the folder and download + extract the zip again. |
| "This download looks incomplete: bin/uv.version is missing. Download the demo again." (Mac) | Same as above, on a Mac. | Delete the folder and download + extract the zip again. |
| "This Mac is not supported." | Your Mac's processor type wasn't recognized. | Check you're on a supported Mac (see "What you need" above); if you believe this is wrong, note your Mac model and contact the team. |
| "First-time setup needs internet once." | The one-time setup needs to download something (either the base software or the detection model) and couldn't reach the internet. | Connect to the internet and double-click the launcher again. |
| "The uv download is damaged. Double-click Start Demo again." | A downloaded file didn't match what was expected — likely an interrupted or corrupted download. | Just double-click the launcher again; it will retry the download. |
| "Could not unpack uv. Double-click Start Demo again." | The downloaded setup file could not be opened/installed. | Double-click the launcher again. If it keeps happening, delete the `bin` folder inside the demo folder and try again. |
| "Using CPU. To retry the NVIDIA GPU, delete the file .uv\cuda-unusable in this folder." (Windows) | Your NVIDIA graphics card couldn't be used once, so the demo is using the regular processor (CPU) instead, which is slower but still works. | If you've since fixed your NVIDIA drivers, or just want to try again, delete the file `.uv\cuda-unusable` inside the demo folder and restart the demo. |
| "NVIDIA GPU not usable — continuing on CPU" | Printed during one-time setup when the NVIDIA graphics card can't be used. Leads to the "Using CPU" message above on the next run. | Nothing needed — the demo will still work, just slower. See the line above if you want to retry the GPU later. |
| "Setup did not finish. Read the message above, then double-click Start Demo again." | The one-time setup hit a problem, described by the message just above this one in the window. | Read the message above it in the black/Terminal window (it will be one of the others in this table), fix that, then double-click the launcher again. |
| "Model file … is missing or damaged. Run setup again." | A detection model file is missing or doesn't match what's expected, found when clicking Go. | Delete the `models` folder inside the demo folder and double-click the launcher again to re-download it. |
| "Downloaded … failed its checksum. Run setup again." | A file downloaded during setup didn't match what was expected. | Double-click the launcher again; it will retry the download. |
| "Camera unavailable: close other apps using it, then click Go." | Another program (a video call app, another browser tab, etc.) is already using the camera. | Close other apps that might be using the camera, then click Go again. |
| "Camera not found: check it is connected, then click Go." | No camera was detected. | Check the camera is plugged in (or built in and not disabled), then click Go again. |
| "Camera access is off for Terminal: System Settings → Privacy & Security → Camera → turn on Terminal, then quit and relaunch the demo." (Mac) | You previously denied the camera permission prompt (which names "Terminal"). | Go to System Settings → Privacy & Security → Camera, turn on Terminal, then fully quit and reopen the demo. |
| "Windows may be blocking desktop apps from the camera: Settings → Privacy & security → Camera → 'Let desktop apps access your camera'." | Windows' camera privacy setting is blocking the demo. | Go to Settings → Privacy & security → Camera and turn on "Let desktop apps access your camera". |
| "People are always tracked — type an object instead." | You typed a word for a person (like "person" or "man") in the object box. People are tracked automatically; you only type the *object* you're looking for. | Type an object instead, like "knife" or "bag". |
| "Already starting — please wait." | You clicked Go again while it was already starting a session. | Wait a moment; it only needs one click. |
| "Missing or invalid token." | The page's link is missing a piece it needs to talk to the demo (this normally only happens if you typed or edited the page's web address by hand). | Reopen the demo from the launcher rather than typing the address yourself. |
| "Something went wrong — click Go to restart" | The demo hit an unexpected internal error and stopped the current session. Details were saved to the log for the team to look at. | Click Go to start a new session. If it keeps happening, tell the team and mention roughly when it happened. |
| "Demo closed — you can close this tab" | You clicked Quit (or closed the launcher window). The demo has fully stopped. | Nothing needed. Close the browser tab if you like, or double-click the launcher again to restart. |

If you see a message that isn't in this table, or a wall of red technical text (a "stack
trace") instead of a plain sentence, please copy it down (or take a screenshot) and tell the
team — that's a bug we want to fix.
