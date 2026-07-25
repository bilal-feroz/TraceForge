import { FPS, sceneFrames } from "../theme";

export type SceneId =
  | "hook"
  | "problem"
  | "product"
  | "baseline"
  | "candidate"
  | "signoz"
  | "rootCause"
  | "patchAudit"
  | "patched"
  | "latency"
  | "trust"
  | "closing";

const order: SceneId[] = [
  "hook",
  "problem",
  "product",
  "baseline",
  "candidate",
  "signoz",
  "rootCause",
  "patchAudit",
  "patched",
  "latency",
  "trust",
  "closing",
];

export type SceneWindow = {
  id: SceneId;
  from: number;
  duration: number;
  to: number;
  startSec: number;
  endSec: number;
};

let cursor = 0;
export const scenes: SceneWindow[] = order.map((id) => {
  const duration = sceneFrames[id];
  const from = cursor;
  cursor += duration;
  return {
    id,
    from,
    duration,
    to: cursor,
    startSec: from / FPS,
    endSec: cursor / FPS,
  };
});

export const sceneById = Object.fromEntries(scenes.map((s) => [s.id, s])) as Record<
  SceneId,
  SceneWindow
>;

export type CaptionCue = {
  scene: SceneId;
  start: number;
  end: number;
  lines: string[];
};

/** Phrase-level burned-in captions, relative to composition start. */
export const captions: CaptionCue[] = [
  {
    scene: "hook",
    start: 20,
    end: 120,
    lines: ["This change passes every unit test."],
  },
  {
    scene: "hook",
    start: 130,
    end: 250,
    lines: ["Under concurrency: 94.40% request failure."],
  },
  {
    scene: "problem",
    start: sceneById.problem.from + 20,
    end: sceneById.problem.from + 200,
    lines: ["The failure appears only under real load."],
  },
  {
    scene: "problem",
    start: sceneById.problem.from + 210,
    end: sceneById.problem.to - 10,
    lines: ["Client symptoms are not enough."],
  },
  {
    scene: "product",
    start: sceneById.product.from + 30,
    end: sceneById.product.to - 20,
    lines: ["Inspect → Stress → Observe → Diagnose → Forge → Audit → Prove"],
  },
  {
    scene: "baseline",
    start: sceneById.baseline.from + 20,
    end: sceneById.baseline.to - 10,
    lines: ["Phase 1 — Baseline: healthy reference"],
  },
  {
    scene: "candidate",
    start: sceneById.candidate.from + 20,
    end: sceneById.candidate.from + 220,
    lines: ["Lower latency ≠ healthier when requests fail early"],
  },
  {
    scene: "candidate",
    start: sceneById.candidate.from + 230,
    end: sceneById.candidate.to - 10,
    lines: ["Client failure rate: 94.40%"],
  },
  {
    scene: "signoz",
    start: sceneById.signoz.from + 20,
    end: sceneById.signoz.from + 280,
    lines: ["SigNoz: 3,158 HTTP 500 · 364 HTTP 201"],
  },
  {
    scene: "signoz",
    start: sceneById.signoz.from + 300,
    end: sceneById.signoz.to - 10,
    lines: ["154 correlated lock-error logs → 0 after patch"],
  },
  {
    scene: "rootCause",
    start: sceneById.rootCause.from + 20,
    end: sceneById.rootCause.to - 10,
    lines: ["Root cause — write lock held during work"],
  },
  {
    scene: "patchAudit",
    start: sceneById.patchAudit.from + 20,
    end: sceneById.patchAudit.to - 10,
    lines: ["Independent audit: scope · grounding · reversible · tests"],
  },
  {
    scene: "patched",
    start: sceneById.patched.from + 20,
    end: sceneById.patched.to - 10,
    lines: ["Verified improvement → SHIP"],
  },
  {
    scene: "latency",
    start: sceneById.latency.from + 20,
    end: sceneById.latency.to - 10,
    lines: ["Silent degradation: 0% errors, P95 103 → 2,376 ms"],
  },
  {
    scene: "trust",
    start: sceneById.trust.from + 20,
    end: sceneById.trust.to - 10,
    lines: ["Control: NO_REGRESSION · Ledger tamper-evident"],
  },
  {
    scene: "closing",
    start: sceneById.closing.from + 20,
    end: sceneById.closing.to - 10,
    lines: ["Don't guess whether a change is safe. Prove it."],
  },
];
