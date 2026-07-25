# TraceForge demo video — render guide

## Layout

```
video/
  assets/screenshots/     # verified SigNoz captures + manifest
  assets/captures/        # optional high-res TraceForge UI captures
  assets/audio/           # narration script + optional WAV clips
  remotion/               # Remotion project (standalone)
  out/                    # rendered MP4 + thumbnail
  NARRATION_SCRIPT.md
  SCREENSHOT_STORYBOARD.md
  YOUTUBE_*.txt|md
  LICENSES.md
```

## Prerequisites

- Node.js 22+
- pnpm 11+
- ~4 GB free disk for Chrome Headless Shell + render cache

## Install

```powershell
cd video/remotion
pnpm install --ignore-workspace
pnpm approve-builds esbuild   # first time only, if postinstall was skipped
```

`--ignore-workspace` is required because the TraceForge root pnpm workspace only includes `apps/*` and `packages/*`.

## Preview in Remotion Studio

```powershell
cd video/remotion
pnpm studio
```

Open the URL printed in the terminal (usually `http://localhost:3000` for Studio — note this is **not** the TraceForge web app).

Composition: **TraceForgeDemo** (1920×1080, 30 fps, ~4980 frames ≈ 2:46).

Still: **TraceForgeThumbnail** (1280×720).

## Optional narration audio

Create `video/.env.local` (gitignored) with **one** of:

```dotenv
OPENAI_API_KEY=...
OPENAI_TTS_VOICE=alloy
```

or

```dotenv
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
```

Never put these keys in the TraceForge root `.env`.

```powershell
cd video
node scripts/generate-narration.mjs
```

If no key is present, the script exits cleanly and the silent render still works.

To play narration in the composition after generating a concatenated `remotion/public/audio/narration-full.wav`, set the composition prop `playNarration: true` in Studio or via:

```powershell
pnpm exec remotion render TraceForgeDemo ../../out/traceforge-demo-youtube.mp4 --props="{\"playNarration\":true,\"debug\":false,\"reducedMotion\":false}"
```

## Draft render (faster, half resolution)

```powershell
cd video/remotion
pnpm render:draft
```

Output: `video/out/traceforge-demo-draft.mp4` (path is relative to `video/remotion`, i.e. `../out/…`)

## Final 1080p render

```powershell
cd video/remotion
pnpm render
```

Output: `video/out/traceforge-demo-youtube.mp4`

Estimated time on a modern laptop: 3–12 minutes depending on CPU/GPU.

## Thumbnail

```powershell
cd video/remotion
pnpm render:thumbnail
```

Output: `video/out/traceforge-youtube-thumbnail.png`

## Quality checks

```powershell
cd video/remotion
pnpm lint
pnpm typecheck
```

Also verify:

- every screenshot path under `public/screenshots/`
- no secrets in frames
- captions do not cover critical dashboard numbers
- duration under 3:00
- YouTube thumbnail readable at phone size

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `ERR_PNPM_IGNORED_BUILDS` / esbuild missing | `pnpm approve-builds esbuild` then reinstall |
| Studio port conflict with TraceForge web | Remotion Studio picks another port; use the printed URL |
| `staticFile` missing screenshot | Copy essentials into `remotion/public/screenshots/` |
| Proof-page Playwright captures fail | Next.js chunk error on stale production server; SigNoz screenshots remain the primary evidence |
| TTS fails | Check `video/.env.local` only; silent render is valid |

## Outputs

| File | Purpose |
| --- | --- |
| `video/out/traceforge-demo-youtube.mp4` | YouTube upload |
| `video/out/traceforge-youtube-thumbnail.png` | Custom thumbnail |
| `video/YOUTUBE_TITLE.txt` | Title |
| `video/YOUTUBE_DESCRIPTION.md` | Description |
| `video/YOUTUBE_CHAPTERS.txt` | Chapters |
| `video/YOUTUBE_TAGS.txt` | Tags |
| `video/YOUTUBE_PINNED_COMMENT.md` | Pinned comment |
