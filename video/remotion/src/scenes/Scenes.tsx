import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Background } from "../components/Background";
import { MetricCard } from "../components/MetricCard";
import { SafeArea } from "../components/SafeArea";
import { ScreenshotFrame } from "../components/ScreenshotFrame";
import { WorkflowTimeline } from "../components/WorkflowTimeline";
import { colors, facts, fonts } from "../theme";

const Title: React.FC<{ children: React.ReactNode; size?: number }> = ({
  children,
  size = 72,
}) => (
  <div
    style={{
      fontFamily: fonts.display,
      fontSize: size,
      fontWeight: 650,
      color: colors.paper,
      lineHeight: 1.1,
      letterSpacing: "-0.02em",
    }}
  >
    {children}
  </div>
);

const Eyebrow: React.FC<{ children: React.ReactNode; color?: string }> = ({
  children,
  color = colors.ember,
}) => (
  <div
    style={{
      fontFamily: fonts.mono,
      fontSize: 20,
      letterSpacing: "0.16em",
      textTransform: "uppercase",
      color,
      marginBottom: 18,
    }}
  >
    {children}
  </div>
);

const Callout: React.FC<{ children: React.ReactNode; tone?: "red" | "amber" | "cyan" | "green" }> = ({
  children,
  tone = "amber",
}) => {
  const border =
    tone === "red"
      ? colors.red
      : tone === "cyan"
        ? colors.cyan
        : tone === "green"
          ? colors.green
          : colors.amber;
  return (
    <div
      style={{
        alignSelf: "flex-start",
        marginTop: 28,
        padding: "16px 22px",
        border: `1px solid ${border}`,
        color: border,
        fontFamily: fonts.mono,
        fontSize: 24,
        letterSpacing: "0.04em",
        background: "rgba(14,17,22,0.72)",
      }}
    >
      {children}
    </div>
  );
};

export const HookScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const failIn = spring({ frame: frame - 90, fps, config: { damping: 180 } });
  const logoIn = spring({ frame: frame - 160, fps, config: { damping: 200 } });

  return (
    <AbsoluteFill>
      <Background accent={frame > 90 ? "red" : "ember"} />
      <SafeArea>
        <Eyebrow>Pre-production proof</Eyebrow>
        <Title size={64}>A harmless-looking change.</Title>
        <div
          style={{
            marginTop: 36,
            display: "grid",
            gridTemplateColumns: "1.1fr 0.9fr",
            gap: 28,
            flex: 1,
          }}
        >
          <div
            style={{
              background: colors.graphitePanel,
              border: `1px solid ${colors.borderStrong}`,
              padding: 28,
              fontFamily: fonts.mono,
              fontSize: 22,
              color: colors.paperMuted,
              lineHeight: 1.55,
            }}
          >
            <div style={{ color: colors.steel, marginBottom: 16 }}>diff · POST /api/visits</div>
            <div>
              <span style={{ color: colors.red }}>- </span>short write, release lock
            </div>
            <div>
              <span style={{ color: colors.green }}>+ </span>BEGIN IMMEDIATE
            </div>
            <div>
              <span style={{ color: colors.green }}>+ </span>hold lock during 80 ms work
            </div>
            <div>
              <span style={{ color: colors.green }}>+ </span>busy_timeout = 10 ms
            </div>
            <div
              style={{
                marginTop: 28,
                display: "inline-block",
                padding: "10px 16px",
                border: `1px solid ${colors.green}`,
                color: colors.green,
              }}
            >
              UNIT TESTS — PASSED
            </div>
          </div>
          <div
            style={{
              opacity: failIn,
              transform: `translateY(${interpolate(failIn, [0, 1], [28, 0], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              })}px)`,
              background: "rgba(224,90,90,0.10)",
              border: `1px solid ${colors.red}`,
              padding: 28,
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
            }}
          >
            <div style={{ fontFamily: fonts.mono, color: colors.red, fontSize: 18, letterSpacing: "0.12em" }}>
              UNDER CONCURRENCY
            </div>
            <div
              style={{
                marginTop: 16,
                fontFamily: fonts.display,
                fontSize: 64,
                fontWeight: 700,
                color: colors.red,
                lineHeight: 1,
              }}
            >
              94.40%
            </div>
            <div style={{ marginTop: 12, fontFamily: fonts.mono, fontSize: 24, color: colors.paper }}>
              REQUEST FAILURE
            </div>
            <div style={{ marginTop: 8, fontFamily: fonts.mono, fontSize: 16, color: colors.steel }}>
              k6 client-side · run {facts.lockRunId.slice(0, 8)}
            </div>
          </div>
        </div>
        <div
          style={{
            opacity: logoIn,
            marginTop: 28,
            fontFamily: fonts.display,
            fontSize: 42,
            fontWeight: 650,
            color: colors.paper,
          }}
        >
          TraceForge
        </div>
      </SafeArea>
    </AbsoluteFill>
  );
};

export const ProblemScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const steps = ["Code change", "CI passes", "Deploy", "2 a.m. incident"];
  return (
    <AbsoluteFill>
      <Background accent="ember" />
      <SafeArea>
        <Eyebrow>The gap</Eyebrow>
        <Title size={58}>Passing tests do not prove production safety.</Title>
        <div style={{ marginTop: 48, display: "flex", alignItems: "center", gap: 18 }}>
          {steps.map((step, index) => {
            const enter = spring({
              frame: frame - index * 12,
              fps,
              config: { damping: 200 },
            });
            const blocked = step === "Deploy";
            return (
              <React.Fragment key={step}>
                <div
                  style={{
                    opacity: enter,
                    padding: "22px 26px",
                    minWidth: 180,
                    textAlign: "center",
                    background: blocked ? "rgba(224,90,90,0.12)" : colors.graphitePanel,
                    border: `1px solid ${blocked ? colors.red : colors.borderStrong}`,
                    color: blocked ? colors.red : colors.paper,
                    fontFamily: fonts.display,
                    fontSize: 28,
                    fontWeight: 600,
                    textDecoration: blocked ? "line-through" : "none",
                  }}
                >
                  {step}
                </div>
                {index < steps.length - 1 ? (
                  <div style={{ color: colors.steel, fontSize: 28 }}>→</div>
                ) : null}
              </React.Fragment>
            );
          })}
        </div>
        <Callout tone="amber">THE FAILURE APPEARS ONLY UNDER REAL LOAD</Callout>
        <div
          style={{
            marginTop: 36,
            maxWidth: 1100,
            fontFamily: fonts.display,
            fontSize: 32,
            color: colors.paperMuted,
            lineHeight: 1.4,
          }}
        >
          Concurrency, latency, and lock regressions stay invisible until production — unless you
          run the experiment and read the server-side truth.
        </div>
      </SafeArea>
    </AbsoluteFill>
  );
};

export const ProductScene: React.FC = () => {
  return (
    <AbsoluteFill>
      <Background accent="cyan" />
      <SafeArea>
        <div style={{ display: "grid", gridTemplateColumns: "1.15fr 0.85fr", gap: 36, flex: 1 }}>
          <div>
            <Eyebrow color={colors.cyan}>TraceForge</Eyebrow>
            <Title size={56}>The full release-proof loop.</Title>
            <div style={{ marginTop: 36 }}>
              <WorkflowTimeline delay={8} />
            </div>
            <div
              style={{
                marginTop: 40,
                fontFamily: fonts.display,
                fontSize: 30,
                color: colors.paperMuted,
                lineHeight: 1.45,
                maxWidth: 900,
              }}
            >
              Deterministic k6 experiments, SigNoz MCP evidence, a minimal patch, an independent
              audit, and an identical rerun before any SHIP verdict.
            </div>
          </div>
          <div
            style={{
              border: `1px solid ${colors.cyan}`,
              background: "rgba(61,184,197,0.08)",
              padding: 28,
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              gap: 18,
            }}
          >
            <div style={{ fontFamily: fonts.mono, color: colors.cyan, letterSpacing: "0.14em" }}>
              EVIDENCE LAYER
            </div>
            <div style={{ fontFamily: fonts.display, fontSize: 42, fontWeight: 650, color: colors.paper }}>
              SigNoz
            </div>
            <div style={{ fontFamily: fonts.mono, fontSize: 20, color: colors.paperMuted, lineHeight: 1.5 }}>
              Traces · Logs · Metrics
              <br />
              queried through official MCP
              <br />
              correlated by traceforge.run.id
            </div>
            <Img
              src={staticFile("captures/control-room.png")}
              style={{
                width: "100%",
                marginTop: 12,
                border: `1px solid ${colors.borderStrong}`,
                objectFit: "cover",
                height: 280,
              }}
            />
          </div>
        </div>
      </SafeArea>
    </AbsoluteFill>
  );
};

export const BaselineScene: React.FC = () => {
  return (
    <AbsoluteFill>
      <Background accent="cyan" />
      <SafeArea>
        <Eyebrow color={colors.cyan}>Phase 1 — Baseline</Eyebrow>
        <Title size={52}>Healthy reference from the unchanged revision.</Title>
        <div style={{ marginTop: 28, display: "grid", gridTemplateColumns: "1.35fr 0.65fr", gap: 28, flex: 1 }}>
          <ScreenshotFrame
            src="screenshots/baseline-01-overview-kpis.png"
            label="SigNoz · TraceForge — Release Proof"
            zoom={1.12}
            focusY={38}
          />
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <MetricCard
              label="Server-side spans"
              value={facts.lock.signoz.baselineSpans}
              hint="SigNoz phase window"
              tone="cyan"
              delay={6}
              width={360}
            />
            <MetricCard
              label="Error spans"
              value={facts.lock.signoz.baselineErrors}
              tone="green"
              delay={12}
              width={360}
            />
            <MetricCard
              label="Server-side P95"
              value={facts.lock.signoz.baselineP95}
              tone="neutral"
              delay={18}
              width={360}
            />
          </div>
        </div>
      </SafeArea>
    </AbsoluteFill>
  );
};

export const CandidateScene: React.FC = () => {
  const frame = useCurrentFrame();
  const warn = interpolate(frame, [40, 90], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill>
      <Background accent="red" />
      <SafeArea>
        <Eyebrow color={colors.red}>Phase 2 — Candidate</Eyebrow>
        <Title size={50}>The tail looks faster. That is the trap.</Title>
        <div style={{ marginTop: 24, display: "grid", gridTemplateColumns: "1.3fr 0.7fr", gap: 28, flex: 1 }}>
          <ScreenshotFrame
            src="screenshots/candidate-01-overview-kpis.png"
            label="Same dashboard · $phase = candidate"
            zoom={1.12}
            focusY={38}
            dim={0.28}
          />
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <MetricCard
              label="k6 client failure"
              value={facts.lock.clientFailureCandidate}
              hint="client-side measurement"
              tone="red"
              delay={4}
              width={380}
            />
            <MetricCard
              label="Server error spans"
              value={`${facts.lock.signoz.candidateErrors} / ${facts.lock.signoz.candidateSpans}`}
              hint={`≈ ${facts.lock.signoz.serverSideErrorPct} server-side`}
              tone="red"
              delay={10}
              width={380}
            />
            <MetricCard
              label="Server-side P95"
              value={facts.lock.signoz.candidateP95}
              hint="lower because failures return early"
              tone="amber"
              delay={16}
              width={380}
            />
            <div
              style={{
                opacity: warn,
                marginTop: 8,
                padding: "16px 18px",
                border: `1px solid ${colors.amber}`,
                color: colors.amber,
                fontFamily: fonts.mono,
                fontSize: 20,
                lineHeight: 1.4,
              }}
            >
              LOWER LATENCY ≠ HEALTHIER
              <br />
              WHEN REQUESTS FAIL EARLY
            </div>
          </div>
        </div>
      </SafeArea>
    </AbsoluteFill>
  );
};

export const SignozScene: React.FC = () => {
  const frame = useCurrentFrame();
  const second = frame > 280;
  return (
    <AbsoluteFill>
      <Background accent="cyan" />
      <SafeArea>
        <Eyebrow color={colors.cyan}>SigNoz evidence</Eyebrow>
        <Title size={48}>Queried through SigNoz MCP — exact run window.</Title>
        <div style={{ marginTop: 22, display: "grid", gridTemplateColumns: "1.25fr 0.75fr", gap: 24, flex: 1 }}>
          <ScreenshotFrame
            src={
              second
                ? "screenshots/candidate-03-lock-logs-slow-operations-traces.png"
                : "screenshots/candidate-02-error-rate-and-status.png"
            }
            label={second ? "Lock errors · correlated traces" : "HTTP status distribution"}
            zoom={1.1}
            focusX={second ? 30 : 72}
            focusY={second ? 35 : 55}
          />
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <MetricCard
              label="HTTP 500 spans"
              value={facts.lock.signoz.candidateHttp500}
              tone="red"
              delay={4}
              width={400}
            />
            <MetricCard
              label="HTTP 201 spans"
              value={facts.lock.signoz.candidateHttp201}
              tone="green"
              delay={10}
              width={400}
            />
            <MetricCard
              label="Endpoint"
              value="POST /api/visits"
              hint={`run ${facts.lockRunId.slice(0, 8)}…`}
              tone="cyan"
              delay={16}
              width={400}
            />
            <div
              style={{
                marginTop: 8,
                padding: 18,
                border: `1px solid ${colors.borderStrong}`,
                background: colors.graphitePanel,
              }}
            >
              <div style={{ fontFamily: fonts.mono, color: colors.steel, fontSize: 15, letterSpacing: "0.1em" }}>
                TRACEFORGE RELEASE-PROOF PROJECTION
              </div>
              <div style={{ marginTop: 12, fontFamily: fonts.display, fontSize: 28, color: colors.paper }}>
                {facts.lock.lockLogsCandidate} correlated lock-error logs
              </div>
              <div style={{ marginTop: 6, fontFamily: fonts.display, fontSize: 28, color: colors.green }}>
                {facts.lock.lockLogsPatched} after patch
              </div>
            </div>
          </div>
        </div>
      </SafeArea>
    </AbsoluteFill>
  );
};

export const RootCauseScene: React.FC = () => {
  return (
    <AbsoluteFill>
      <Background accent="ember" />
      <SafeArea>
        <Eyebrow>Root cause</Eyebrow>
        <Title size={52}>Write lock held during work.</Title>
        <div style={{ marginTop: 36, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 28 }}>
          <div
            style={{
              background: colors.graphitePanel,
              border: `1px solid ${colors.borderStrong}`,
              padding: 32,
              fontFamily: fonts.mono,
              fontSize: 26,
              lineHeight: 1.7,
              color: colors.paperMuted,
            }}
          >
            <div style={{ color: colors.ember }}>BEGIN IMMEDIATE</div>
            <div>80 ms simulated work</div>
            <div>while write lock is held</div>
            <div style={{ marginTop: 18, color: colors.red }}>busy_timeout = 10 ms</div>
          </div>
          <div
            style={{
              background: colors.graphitePanel,
              border: `1px solid ${colors.borderStrong}`,
              padding: 32,
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              gap: 18,
            }}
          >
            <div style={{ fontFamily: fonts.mono, color: colors.steel, letterSpacing: "0.12em" }}>
              CLASSIFICATION
            </div>
            <div style={{ fontFamily: fonts.display, fontSize: 40, fontWeight: 650, color: colors.red }}>
              {facts.lock.classification}
            </div>
            <div style={{ fontFamily: fonts.display, fontSize: 28, color: colors.paperMuted }}>
              Evidence-backed. Reviewable. Not inferred from the diff alone.
            </div>
          </div>
        </div>
        <Callout tone="red">ROOT CAUSE — WRITE LOCK HELD DURING WORK</Callout>
      </SafeArea>
    </AbsoluteFill>
  );
};

export const PatchAuditScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const checks = [
    "EVIDENCE GROUNDED",
    "SCOPE VALID",
    "TESTS PASSED",
    "REVERSIBLE",
    "IDENTICAL LOAD PLAN",
  ];
  return (
    <AbsoluteFill>
      <Background accent="ember" />
      <SafeArea>
        <div style={{ display: "grid", gridTemplateColumns: "1.05fr 0.95fr", gap: 28, flex: 1 }}>
          <div>
            <Eyebrow>Patch + audit</Eyebrow>
            <Title size={50}>Smallest relevant fix. Independently audited.</Title>
            <div style={{ marginTop: 28, display: "flex", flexDirection: "column", gap: 12 }}>
              {checks.map((check, index) => {
                const enter = spring({
                  frame: frame - 12 - index * 10,
                  fps,
                  config: { damping: 200 },
                });
                return (
                  <div
                    key={check}
                    style={{
                      opacity: enter,
                      display: "flex",
                      alignItems: "center",
                      gap: 14,
                      padding: "16px 18px",
                      border: `1px solid ${colors.green}`,
                      background: "rgba(61,191,122,0.08)",
                      color: colors.green,
                      fontFamily: fonts.mono,
                      fontSize: 24,
                    }}
                  >
                    <span>✓</span>
                    <span>{check}</span>
                  </div>
                );
              })}
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Img
              src={staticFile("captures/lock-patch.png")}
              style={{
                width: "100%",
                flex: 1,
                objectFit: "cover",
                border: `1px solid ${colors.borderStrong}`,
                background: colors.graphitePanel,
              }}
            />
            <div style={{ fontFamily: fonts.mono, fontSize: 16, color: colors.steel }}>
              TraceForge patch view · sandbox only · source checkout untouched
            </div>
          </div>
        </div>
      </SafeArea>
    </AbsoluteFill>
  );
};

export const PatchedScene: React.FC = () => {
  return (
    <AbsoluteFill>
      <Background accent="green" />
      <SafeArea>
        <Eyebrow color={colors.green}>Phase 3 — Patched proof</Eyebrow>
        <Title size={50}>Identical experiment. Verified improvement.</Title>
        <div style={{ marginTop: 24, display: "grid", gridTemplateColumns: "1.25fr 0.75fr", gap: 24, flex: 1 }}>
          <ScreenshotFrame
            src="screenshots/patched-01-overview-kpis.png"
            label="SigNoz · $phase = patched"
            zoom={1.12}
            focusY={38}
            dim={0.25}
          />
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <MetricCard
              label="Candidate failures"
              value={facts.lock.clientFailureCandidate}
              tone="red"
              delay={4}
              width={400}
            />
            <MetricCard
              label="Patched failures"
              value={facts.lock.k6.patchedFail}
              hint="k6 client-side"
              tone="green"
              delay={10}
              width={400}
            />
            <MetricCard
              label="Lock-error logs"
              value={`${facts.lock.lockLogsCandidate} → ${facts.lock.lockLogsPatched}`}
              hint="release-proof projection"
              tone="green"
              delay={16}
              width={400}
            />
            <div
              style={{
                marginTop: 8,
                padding: "22px 20px",
                border: `1px solid ${colors.green}`,
                background: "rgba(61,191,122,0.12)",
              }}
            >
              <div style={{ fontFamily: fonts.mono, color: colors.green, letterSpacing: "0.12em" }}>
                {facts.lock.verification}
              </div>
              <div
                style={{
                  marginTop: 10,
                  fontFamily: fonts.display,
                  fontSize: 56,
                  fontWeight: 700,
                  color: colors.green,
                }}
              >
                {facts.lock.verdict}
              </div>
            </div>
          </div>
        </div>
      </SafeArea>
    </AbsoluteFill>
  );
};

export const LatencyScene: React.FC = () => {
  return (
    <AbsoluteFill>
      <Background accent="amber" />
      <SafeArea>
        <Eyebrow color={colors.amber}>Second case · silent degradation</Eyebrow>
        <Title size={50}>Zero errors. Still broken.</Title>
        <div style={{ marginTop: 36, display: "flex", gap: 18, flexWrap: "wrap" }}>
          <MetricCard label="Failure rate" value={facts.latency.failureRate} tone="green" delay={4} />
          <MetricCard
            label="P95 baseline → candidate"
            value={`${facts.latency.p95Baseline} → ${facts.latency.p95Candidate}`}
            tone="red"
            delay={10}
            width={520}
          />
          <MetricCard label="Slope" value={facts.latency.slope} tone="amber" delay={16} width={360} />
          <MetricCard
            label="Patched P95"
            value={facts.latency.p95Patched}
            tone="green"
            delay={22}
            width={300}
          />
        </div>
        <Callout tone="amber">
          {facts.latency.classification} → {facts.latency.verdict}
        </Callout>
        <div
          style={{
            marginTop: 28,
            fontFamily: fonts.mono,
            fontSize: 18,
            color: colors.steel,
          }}
        >
          run {facts.latencyRunId}
        </div>
      </SafeArea>
    </AbsoluteFill>
  );
};

export const TrustScene: React.FC = () => {
  return (
    <AbsoluteFill>
      <Background accent="cyan" />
      <SafeArea>
        <Eyebrow color={colors.cyan}>Control · ledger · self-observability</Eyebrow>
        <Title size={48}>Restraint, receipts, and the agent watching itself.</Title>
        <div style={{ marginTop: 28, display: "grid", gridTemplateColumns: "1.15fr 0.85fr", gap: 24, flex: 1 }}>
          <ScreenshotFrame
            src="screenshots/candidate-04-correlated-evidence-and-stage-spans.png"
            label="traceforge-orchestrator · workflow + MCP spans"
            zoom={1.08}
            focusY={60}
          />
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <MetricCard
              label="Control case"
              value={facts.control.classification}
              hint="no patch generated"
              tone="green"
              delay={4}
              width={420}
            />
            <MetricCard
              label="Workflow stages"
              value={String(facts.selfObs.workflowStages)}
              hint={`${facts.selfObs.mcpCalls} signoz.mcp.call spans`}
              tone="cyan"
              delay={10}
              width={420}
            />
            <MetricCard
              label="Ledger"
              value="VALID"
              hint={`tampered copy → ${facts.ledger.tamperResult}`}
              tone="green"
              delay={16}
              width={420}
            />
          </div>
        </div>
      </SafeArea>
    </AbsoluteFill>
  );
};

export const ClosingScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 200 } });
  return (
    <AbsoluteFill>
      <Background accent="ember" />
      <SafeArea>
        <div
          style={{
            opacity: enter,
            flex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "flex-start",
            gap: 22,
          }}
        >
          <Eyebrow>TraceForge</Eyebrow>
          <Title size={84}>TRACEFORGE</Title>
          <div
            style={{
              fontFamily: fonts.display,
              fontSize: 40,
              fontWeight: 600,
              color: colors.emberSoft,
              maxWidth: 1200,
              lineHeight: 1.25,
            }}
          >
            Don&apos;t guess whether a change is safe.
            <br />
            Prove it.
          </div>
          <div
            style={{
              marginTop: 12,
              fontFamily: fonts.mono,
              fontSize: 24,
              color: colors.paperMuted,
              lineHeight: 1.6,
            }}
          >
            LOAD-TEST THE CHANGE.
            <br />
            READ THE TRUTH FROM SIGNOZ.
            <br />
            WRITE AND VERIFY THE FIX.
          </div>
          <div
            style={{
              marginTop: 28,
              fontFamily: fonts.mono,
              fontSize: 26,
              color: colors.cyan,
            }}
          >
            {facts.repoUrl}
          </div>
        </div>
      </SafeArea>
    </AbsoluteFill>
  );
};
