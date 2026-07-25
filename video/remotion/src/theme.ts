export const colors = {
  graphite: "#0E1116",
  graphiteRaised: "#161B22",
  graphitePanel: "#1C232D",
  steel: "#8B949E",
  steelDim: "#5C6570",
  paper: "#F0F3F6",
  paperMuted: "#C9D1D9",
  ember: "#E86B2C",
  emberSoft: "#F0A060",
  cyan: "#3DB8C5",
  cyanSoft: "#7AD4DD",
  red: "#E05A5A",
  green: "#3DBF7A",
  amber: "#D4A017",
  border: "rgba(240, 243, 246, 0.10)",
  borderStrong: "rgba(240, 243, 246, 0.18)",
} as const;

export const fonts = {
  display:
    '"IBM Plex Sans", "Segoe UI", "Helvetica Neue", Arial, sans-serif',
  mono: '"IBM Plex Mono", "Cascadia Code", "Consolas", monospace',
} as const;

/** Verified facts only — never invent numbers. */
export const facts = {
  lockRunId: "50ef7693-1eb8-4050-8ae8-1de5c76f83b2",
  latencyRunId: "45674c9c-bc70-4e64-9664-8bb9ae0ad1bf",
  controlRunId: "a53f317c-a4c9-4843-8441-9cb3fa0f3da9",
  lock: {
    classification: "ERROR_RATE_REGRESSION",
    verification: "VERIFIED_IMPROVEMENT",
    verdict: "SHIP",
    clientFailureCandidate: "94.40%",
    clientFailurePatched: "0.16%",
    // Product release-proof projection (exact phase-window attribution)
    lockLogsCandidate: 154,
    lockLogsPatched: 0,
    // SigNoz dashboard tiles for the same run
    signoz: {
      baselineSpans: "5,522",
      baselineErrors: "3",
      baselineP95: "600.85 ms",
      candidateSpans: "3,522",
      candidateErrors: "3,158",
      candidateP95: "281.15 ms",
      candidateHttp500: "3,158",
      candidateHttp201: "364",
      patchedSpans: "5,633",
      patchedErrors: "5",
      patchedP95: "605.2 ms",
      serverSideErrorPct: "89.7%",
    },
    k6: {
      baselineRequests: "5,524",
      baselineFail: "0.09%",
      baselineP95: "601.93 ms",
      candidateRequests: "6,499",
      candidateFail: "94.40%",
      candidateP95: "340.19 ms",
      patchedRequests: "5,637",
      patchedFail: "0.16%",
      patchedP95: "605.61 ms",
    },
  },
  latency: {
    classification: "SILENT_DEGRADATION",
    verdict: "SHIP",
    failureRate: "0.00%",
    p95Baseline: "103.91 ms",
    p95Candidate: "2,376.92 ms",
    p95Patched: "92.85 ms",
    slope: "+320.99 ms / window",
  },
  control: {
    classification: "NO_REGRESSION",
    verdict: "SHIP",
    patchGenerated: false,
  },
  selfObs: {
    workflowStages: 15,
    mcpCalls: 33,
    k6ExecutePhases: 3,
  },
  ledger: {
    events: 16,
    originalValid: true,
    tamperResult: "event hash mismatch",
  },
  repoUrl: "github.com/bilal-feroz/TraceForge",
} as const;

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

/** Scene lengths in frames (30 fps). Total ≈ 2:50. */
export const sceneFrames = {
  hook: 270,
  problem: 420,
  product: 480,
  baseline: 390,
  candidate: 510,
  signoz: 660,
  rootCause: 390,
  patchAudit: 450,
  patched: 480,
  latency: 390,
  trust: 330,
  closing: 210,
} as const;

export const TOTAL_FRAMES = (
  Object.values(sceneFrames) as number[]
).reduce((a: number, b: number) => a + b, 0);
