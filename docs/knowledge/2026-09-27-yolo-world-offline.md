---
title: Running YOLO-World fully offline (ultralytics 8.4.163)
date: 2026-09-27
tags: [model, offline, ultralytics, clip]
status: verified
---

# Running YOLO-World fully offline

## Observed

1. **CLIP import triggers a runtime pip install.** `ultralytics/nn/text_model.py` does
   `try: import clip` / `except ImportError: checks.check_requirements("git+https://github.com/ultralytics/CLIP.git")`.
   With `YOLO_AUTOINSTALL=False` that path logs a warning and skips pip, but the demo would
   then fail on the second `import clip`.
2. **CLIP weights download on first `set_classes`.** `WorldModel.get_text_pe` builds
   `build_text_model("clip:ViT-B/32")` → `clip.load("ViT-B/32", download_root=WEIGHTS_DIR / "clip")`.
   `WEIGHTS_DIR` comes from the Ultralytics settings (`<git root or cwd>/weights`), and
   `clip._download` fetches from `openaipublic.azureedge.net` if the file is absent. It is only
   built if `model.clip_model` is unset — and the `yolov8*-worldv2.pt` checkpoints do not carry one.
3. **Ultralytics falls back to `<cwd>/Ultralytics` for its settings** when the directory
   named by `YOLO_CONFIG_DIR` does not exist yet (`get_user_config_dir` only creates
   `YOLO_CONFIG_DIR/Ultralytics` if its parent is writable-and-existing). Without
   `YOLO_CONFIG_DIR` at all, it writes `%APPDATA%\Ultralytics\settings.json` on first import.
4. `YOLO_OFFLINE=1` makes `is_online()` return False without any DNS query, so `ONLINE` is
   False, which also disables Ultralytics analytics events (`Events.enabled` requires `ONLINE`).

## Evidence

- Dependency: `clip @ https://github.com/ultralytics/CLIP/archive/a13192f8cb767260d7dfd98c843b0716593169e7.zip`
  in `pyproject.toml`; `bin/uv.exe lock` records it with
  `sdist = { hash = "sha256:6cbb15f8dee15645d9e5a4e51c7a7166fd6c33465c101e5d4377e2459341fa20" }`.
  Hatchling needs `[tool.hatch.metadata] allow-direct-references = true` for this.
- CLIP weights: `models/ViT-B-32.pt`, SHA-256 `40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af`
  (identical to the hash embedded in the openai URL), pinned in `models/manifest.json`.
- `demo/detector.py::YoloWorldDetector` builds Ultralytics' own text model as
  `ultralytics.nn.text_model.CLIP("<models>/ViT-B-32.pt", device)` — `clip.load` of a file
  path never downloads — and assigns it to `model.model.clip_model` before `set_classes`, so
  step 2's download path is never reached. `ultralytics==8.4.163` is pinned exactly in
  `pyproject.toml` because this relies on `WorldModel.clip_model`.
- `tests/offline/test_offline.py` (pytest-socket `allow_hosts=["127.0.0.1"]`, non-local DNS
  and `pip` subprocesses fail, shallow mtime snapshot of `~`, `~/.cache{,/clip,/torch}`,
  the Ultralytics settings dirs for all three OSes, `models/` and cwd) passes.
  Mutation check: removing the `clip_model` assignment fails the test with
  `DNS lookup attempted: openaipublic.azureedge.net`.
- The first test run (before `_set_env` created the dirs) left `./Ultralytics/settings.json`
  in the worktree — the fallback in observation 3.
- With `clip` hidden (`sys.modules["clip"] = None`), `YOLO_AUTOINSTALL=False` and
  `subprocess.check_output`/`run` patched to abort, importing `ultralytics.nn.text_model`
  raises `ImportError` without calling pip.

## Implication

- Keep `clip` as a hashed archive-URL dependency; bumping it means a new commit SHA and `uv lock`.
- Always construct the detector through `YoloWorldDetector` (it pre-sets `clip_model`);
  calling Ultralytics' `set_classes` on a fresh `YOLOWorld` would try the network.
- `demo.__main__._set_env` must create `YOLO_CONFIG_DIR`, `TORCH_HOME` and `XDG_CACHE_HOME`
  before Ultralytics is imported; the offline test does the same.
- If Ultralytics is upgraded (deliberately: it is pinned), re-check `WorldModel.get_text_pe`
  still honours a pre-set `clip_model`, then re-run `tests/offline`.
- The offline test also fails if `./weights/clip` appears (the download dir Ultralytics would
  create in cwd), as seen in the mutation run.
