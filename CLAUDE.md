# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **local, single-user, lightweight web app** for reviewing/correcting YOLO-format object-detection annotations. Not a general annotation platform — deliberately scoped to the **person-detection** review loop only: there is intentionally no class-picker UI, no class names, no class colors. Every new box is written as `class_id = 0`. Existing non-zero class ids from baseline label files round-trip on save (we don't mutate them) but the UI doesn't distinguish them visually.

If the user later wants multi-class support, that's a UI re-introduction (sidebar + color-per-class + 1–9 keys) — don't add it pre-emptively.

## Run it

Dependencies are managed by **pixi** (see [pixi.toml](pixi.toml)). Do not use pip / requirements.txt.

```powershell
pixi install                                          # one-time, creates .pixi/ env
pixi run python app.py                                # uses ./images and ./labels
pixi run python app.py <images_dir> [labels_dir]      # or pass them explicitly
# then open http://127.0.0.1:5000
```

- Two-folder layout: images come from `images_dir`, YOLO `.txt` files come from `labels_dir`. Both default to `./images` and `./labels` respectively when no CLI args are given. **All writes go to `labels_dir`** — it doubles as the output folder, overwriting baseline labels in place. If the user wants a separate output folder later, add a `--output` flag rather than changing this default silently.
- Optional `--port N` to change port.
- The folders you pass *are* the state — no database, no per-user config, no project concept. Edits write straight back to the matching `.txt` file (one `.txt` per image, same stem).

## Architecture

Two files do all the work:

- [app.py](app.py) — Flask backend, ~100 lines. CLI entry point that takes one or two folders, lists images, and exposes a tiny JSON API:
  - `GET /` → annotation review page
  - `GET /browse` → tile-grid browse page with per-image delete buttons
  - `GET /api/images` → list of image filenames in `images_dir`
  - `GET /api/image/<name>` → raw image bytes
  - `DELETE /api/image/<name>` → removes the image file AND its matching `.txt` from `labels_dir`; if the bookmark pointed at it, clears the bookmark too. Idempotent in spirit but returns 404 if the name isn't currently listed.
  - `GET /api/annotations/<name>` → parsed YOLO boxes as JSON `[{class_id,x,y,w,h,score?}, …]` (normalized 0–1). Accepts **5-column ground truth** or **6-column predictions with confidence** on read; `score` is only present for 6-column inputs.
  - `POST /api/annotations/<name>` → writes the YOLO `.txt` back as 5 columns (confidence is dropped — once a human edits, the detector's score no longer applies)
  - `GET /api/bookmark` / `POST /api/bookmark` → reads/writes `labels_dir/.bookmark` (single-line file holding the last-viewed image filename). The frontend writes this on every navigation and reads it on startup, so a fresh page load resumes at wherever the user last was. If the bookmarked file no longer exists in the folder, it silently falls back to image 0.
- [templates/index.html](templates/index.html) — annotation review UI in one file: HTML + CSS + vanilla JS, no build step, no dependencies. Renders the image to a `<canvas>` and overlays boxes; all hit-testing, drag/resize, and rendering happens in JS using a fit-to-window letterbox transform. Accepts a `?image=NAME` query param (sent by the browse view's tile links) that takes precedence over the bookmark when picking which image to open.
- [templates/browse.html](templates/browse.html) — tile-grid browser. Each tile is a thumbnail link back to `/?image=<name>` plus a per-tile Delete button. Multi-select: click the corner checkbox to toggle, Shift+click for range, `Select all` toggles every tile, Esc clears. With ≥1 selected, a `Delete selected` button appears that bulk-deletes via parallel `DELETE /api/image/<name>` calls (confirms once, fails partially with an alert listing the count). Per-tile Delete remains for one-off use.

Key invariant: **boxes are always stored in YOLO normalized format** (`x_center, y_center, width, height`, all 0–1). The canvas code converts to/from pixel space only for display and mouse math — server-side I/O is pure normalized round-trip with 6-decimal precision.

## UX contract (matches the README)

Keyboard-driven verifier flow:

- **A** — enter add mode (next click-drag draws a new box, then returns to select mode)
- **D** / Delete — delete the selected box
- **M** / Esc — return to select/modify mode (cancel add, deselect)
- **← / →** — prev/next image (auto-saves dirty state before navigating)
- **S** / Ctrl+S — explicit save
- **U** — update-forward: copy the current image's boxes onto the next N images (N comes from the "Update fwd" number input in the topbar; default 5). Designed for video-frame sequences a few seconds apart where the same person stays roughly in place; the targets' existing labels are overwritten. No wrap-around at end of list. If the current image has zero boxes the action no-ops with a "nothing to paste" flash.

Default mouse mode is always select/modify: click a box to select, drag its body to move, drag a corner handle to resize. Add mode is a one-shot toggle.

The topbar also has a `Jump` number input with a `Go` button (or press Enter) for hopping directly to a specific image index (1-based, out-of-range values flash a warning). Out-of-input typing never triggers shortcut keys because the global keydown handler ignores events whose target is an `<input>`.

Topbar shows a `saved` / `unsaved` status indicator; `beforeunload` warns if dirty.

## When extending

The current build is intentionally the v1 minimum (load folder · draw/move/delete boxes · class colors · prev/next · save). Deferred for later iterations: zoom/pan, undo, jump-to-image-N, toggle label visibility, hide/lock specific classes. Add these as small additions inside the existing two files rather than splitting into a framework — the "single HTML file, single Python file" shape is part of the design.

Out of scope on purpose (don't add unless the user asks):
- Polygons / keypoints / segmentation / tracking
- COCO / Pascal VOC / other formats — YOLO only
- Multi-user, auth, projects, datasets concept
- Model-in-the-loop / active learning / auto-suggestions
