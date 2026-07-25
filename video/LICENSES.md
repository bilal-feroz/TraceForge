# Licenses for video assets

## Screenshots

| Asset | Source | License / notes |
| --- | --- | --- |
| `assets/screenshots/*.png` | Real SigNoz Cloud dashboard captures from run `50ef7693-1eb8-4050-8ae8-1de5c76f83b2` | Product UI captures for documentation/demo of the author's own TraceForge run. Unmodified originals. |
| `assets/captures/control-room.png` | Local TraceForge frontend at `127.0.0.1:3000` | Author's own product UI. |
| `assets/captures/lock-patch.png` | Local TraceForge frontend | Author's own product UI. |
| `assets/captures/lock-evidence.png` | Local TraceForge frontend | Author's own product UI. |

Failed/partial captures that show Next.js error pages are retained for diagnosis only and are **not** used in the composition.

## Fonts

| Font | Usage | License |
| --- | --- | --- |
| Segoe UI / Helvetica Neue / Arial / Consolas system stacks | Display and mono typography in Remotion | System fonts. No bundling of proprietary font files. |

## Music

No background music track is bundled.

If music is added later, it must be properly licensed (CC0 / royalty-free with redistribution rights) and listed here before commit. Prefer a silent or SFX-only mix over unlicensed audio.

## Sound effects

No external SFX library is currently bundled. Impact/alert tones, if added, must be original or CC0 and listed here.

## Narration

Narration audio is generated optionally via OpenAI TTS or ElevenLabs when a key is present in `video/.env.local` (gitignored). Generated WAV files under `assets/audio/narration/` are gitignored. The spoken script text in `NARRATION_SCRIPT.md` is original TraceForge documentation.

## Third-party software

| Package | License |
| --- | --- |
| Remotion and `@remotion/*` | Remotion license (free for teams ≤ 3) — see https://www.remotion.pro/license |
| React / React DOM | MIT |
| Playwright (capture tooling) | Apache-2.0 |

## Branding

No third-party product logos are copied into this video package beyond what appears inside authentic SigNoz dashboard screenshots of the author's own account and run.
