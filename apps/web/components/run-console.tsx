"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ReleaseProofView } from "@/components/release-proof";
import { Availability, StatusBadge } from "@/components/status";
import { API_URL, cancelRun, getRun } from "@/lib/api";
import type { Run, Stage } from "@/lib/types";

const stages: Array<{ stage: Stage; verb: string }> = [
  { stage: "CREATED", verb: "Intake" },
  { stage: "REPOSITORY_VALIDATED", verb: "Validate" },
  { stage: "CHANGE_INSPECTED", verb: "Inspect" },
  { stage: "ENDPOINTS_SCOPED", verb: "Scope" },
  { stage: "LOAD_PLAN_CREATED", verb: "Plan" },
  { stage: "K6_SCRIPT_VALIDATED", verb: "Compile" },
  { stage: "BASELINE_COMPLETED", verb: "Baseline" },
  { stage: "CANDIDATE_COMPLETED", verb: "Stress" },
  { stage: "TELEMETRY_CONFIRMED", verb: "Observe" },
  { stage: "SIGNALS_CORRELATED", verb: "Correlate" },
  { stage: "REGRESSION_CLASSIFIED", verb: "Diagnose" },
  { stage: "PATCH_PROPOSED", verb: "Forge" },
  { stage: "PATCH_AUDITED", verb: "Audit" },
  { stage: "PATCH_SANDBOXED", verb: "Sandbox" },
  { stage: "VERIFICATION_COMPLETED", verb: "Prove" },
  { stage: "VERDICT_PUBLISHED", verb: "Verdict" },
];

type View = "live" | "evidence" | "diagnosis" | "patch" | "proof";

function format(value: number, digits = 1) {
  return Number.isFinite(value) ? value.toFixed(digits) : "—";
}

function Metric({
  label,
  value,
  detail,
  tone = "neutral",
}: {
  label: string;
  value: string;
  detail: string;
  tone?: "neutral" | "cyan" | "red" | "green";
}) {
  const color = {
    neutral: "text-[var(--paper)]",
    cyan: "text-[var(--cyan)]",
    red: "text-[var(--red)]",
    green: "text-[var(--green)]",
  }[tone];
  return (
    <div className="border-r border-white/10 p-5 last:border-r-0">
      <p className="eyebrow">{label}</p>
      <p className={`mono mt-3 text-2xl font-medium ${color}`}>{value}</p>
      <p className="mt-2 text-xs text-[var(--steel-500)]">{detail}</p>
    </div>
  );
}

function MetricComparison({ run }: { run: Run }) {
  const baseline = run.experiments.baseline;
  const candidate = run.experiments.candidate;
  const patched = run.experiments.patched;
  if (!baseline && !candidate) {
    return (
      <div className="panel-inset p-6 text-sm text-[var(--steel-300)]">
        Load results will appear after the first experiment completes.
      </div>
    );
  }
  return (
    <div className="panel overflow-hidden">
      <div className="metric-grid">
        <Metric
          detail={`baseline ${format(baseline?.stats.p95_ms ?? NaN)} ms`}
          label="Candidate P95"
          tone={candidate?.stats.threshold_failures.length ? "red" : "cyan"}
          value={`${format(candidate?.stats.p95_ms ?? NaN)} ms`}
        />
        <Metric
          detail={`baseline ${format((baseline?.stats.failure_rate ?? NaN) * 100, 2)}%`}
          label="Failure rate"
          tone={(candidate?.stats.failure_rate ?? 0) > 0.05 ? "red" : "cyan"}
          value={`${format((candidate?.stats.failure_rate ?? NaN) * 100, 2)}%`}
        />
        <Metric
          detail={`baseline ${format(baseline?.stats.rate ?? NaN)} req/s`}
          label="Throughput"
          tone="cyan"
          value={`${format(candidate?.stats.rate ?? NaN)} req/s`}
        />
        <Metric
          detail={patched ? "patched phase recorded" : "awaiting sandbox proof"}
          label="Patched P95"
          tone={patched ? "green" : "neutral"}
          value={patched ? `${format(patched.stats.p95_ms)} ms` : "—"}
        />
      </div>
    </div>
  );
}

function Timeline({ run }: { run: Run }) {
  const currentIndex = stages.findIndex((item) => item.stage === run.stage);
  return (
    <ol aria-label="Run state machine" className="space-y-1">
      {stages.map((item, index) => {
        const complete = index < currentIndex || Boolean(run.terminal_state);
        const current = index === currentIndex && !run.terminal_state;
        return (
          <li className="relative flex gap-3 py-2" key={item.stage}>
            {index < stages.length - 1 && (
              <span
                aria-hidden="true"
                className={`absolute top-8 left-[7px] h-[calc(100%-16px)] w-px ${
                  complete ? "bg-[var(--ember)]/50" : "bg-white/10"
                }`}
              />
            )}
            <span
              aria-hidden="true"
              className={`relative mt-1 size-[15px] border ${
                complete
                  ? "border-[var(--ember)] bg-[var(--ember)]"
                  : current
                    ? "live-pulse border-[var(--ember)] bg-[rgba(255,122,50,.22)]"
                    : "border-white/20 bg-[var(--graphite-950)]"
              }`}
            />
            <div className="min-w-0">
              <span
                className={`mono block text-[0.68rem] font-semibold tracking-[.06em] ${
                  current ? "text-[var(--ember)]" : complete ? "text-[var(--paper)]" : "text-[var(--steel-500)]"
                }`}
              >
                {item.verb}
              </span>
              <span className="mono mt-0.5 block truncate text-[0.56rem] text-[var(--steel-500)]">
                {item.stage}
              </span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function EvidenceView({ run }: { run: Run }) {
  const candidate = run.telemetry.candidate;
  const traces = candidate?.traces ?? [];
  const logs = candidate?.logs ?? [];
  return (
    <div className="space-y-6">
      <MetricComparison run={run} />
      <section className="panel">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-5 py-4">
          <div>
            <p className="eyebrow">SigNoz / exact window</p>
            <h2 className="mt-1 text-lg font-medium">Server evidence</h2>
          </div>
          <Availability
            available={Boolean(candidate?.available)}
            availableText={`${candidate?.service_name ?? "service"} confirmed`}
            unavailableText="SigNoz verification unavailable"
          />
        </div>
        {!candidate?.available ? (
          <div className="p-6">
            <p className="text-sm text-[var(--amber)]">
              {candidate?.unavailable_reason ?? "Server evidence has not arrived."}
            </p>
            <p className="mt-3 text-xs leading-5 text-[var(--steel-500)]">
              Client metrics remain visible, but TraceForge will not turn them into a server-side
              root-cause claim.
            </p>
          </div>
        ) : (
          <div className="grid lg:grid-cols-2">
            <div className="border-b border-white/10 p-5 lg:border-r lg:border-b-0">
              <p className="eyebrow mb-3">Window</p>
              <p className="mono text-xs leading-6 text-[var(--cyan)]">
                {new Date(candidate.window.started_at).toISOString()}
                <br />→ {new Date(candidate.window.ended_at).toISOString()}
              </p>
            </div>
            <div className="p-5">
              <p className="eyebrow mb-3">MCP calls</p>
              <p className="mono text-2xl">{candidate.mcp_invocations.length}</p>
              <p className="mt-2 text-xs text-[var(--steel-500)]">
                {candidate.tools_discovered.length} tools discovered at runtime
              </p>
            </div>
          </div>
        )}
      </section>
      <section className="panel overflow-x-auto">
        <div className="border-b border-white/10 px-5 py-4">
          <p className="eyebrow">Slow spans</p>
        </div>
        {traces.length === 0 ? (
          <p className="p-6 text-sm text-[var(--steel-500)]">No correlated spans retrieved.</p>
        ) : (
          <table className="w-full min-w-[680px] text-left">
            <thead className="eyebrow border-b border-white/10 text-[.6rem]">
              <tr>
                <th className="px-5 py-3">Operation</th>
                <th className="px-5 py-3">Duration</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Trace ID</th>
              </tr>
            </thead>
            <tbody>
              {traces.slice(0, 20).map((trace) => (
                <tr className="border-b border-white/[.06]" key={`${trace.trace_id}-${trace.span_id}`}>
                  <td className="px-5 py-3 text-sm">{trace.operation}</td>
                  <td className="mono px-5 py-3 text-xs text-[var(--cyan)]">
                    {format(trace.duration_ms)} ms
                  </td>
                  <td className="mono px-5 py-3 text-xs">{trace.status}</td>
                  <td className="mono px-5 py-3 text-xs text-[var(--steel-300)]">
                    {trace.trace_id}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <section className="panel">
        <div className="border-b border-white/10 px-5 py-4">
          <p className="eyebrow">Correlated logs</p>
        </div>
        {logs.length === 0 ? (
          <p className="p-6 text-sm text-[var(--steel-500)]">No correlated log records retrieved.</p>
        ) : (
          <ul className="divide-y divide-white/[.06]">
            {logs.slice(0, 20).map((log, index) => (
              <li className="grid gap-2 px-5 py-4 sm:grid-cols-[120px_1fr]" key={`${log.timestamp}-${index}`}>
                <span className="mono text-[.66rem] text-[var(--steel-500)]">{log.severity}</span>
                <span className="mono text-xs leading-5 text-[var(--steel-300)]">{log.body}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function DiagnosisView({ run }: { run: Run }) {
  const diagnosis = run.diagnosis;
  if (!diagnosis) {
    return (
      <div className="panel p-8">
        <p className="eyebrow mb-3">Diagnosis pending</p>
        <h2 className="text-2xl font-medium">Evidence has not cleared the diagnosis gate.</h2>
        <p className="mt-4 max-w-2xl text-sm leading-6 text-[var(--steel-300)]">
          TraceForge requires candidate load plus correlated SigNoz traces and logs before it names a
          root cause.
        </p>
      </div>
    );
  }
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
      <section className="panel p-6">
        <p className="eyebrow">Classification</p>
        <h2 className="mono mt-3 text-2xl text-[var(--red)]">{diagnosis.classification}</h2>
        <p className="mt-6 text-xl leading-8">{diagnosis.likely_root_cause}</p>
        <div className="mt-8 grid gap-px bg-white/10 sm:grid-cols-2">
          <div className="bg-[var(--graphite-900)] p-4">
            <p className="eyebrow">Affected endpoint</p>
            <p className="mono mt-2 text-sm text-[var(--cyan)]">{diagnosis.affected_endpoint}</p>
          </div>
          <div className="bg-[var(--graphite-900)] p-4">
            <p className="eyebrow">Confidence</p>
            <p className="mono mt-2 text-sm">{format(diagnosis.confidence * 100, 0)}%</p>
          </div>
          <div className="bg-[var(--graphite-900)] p-4">
            <p className="eyebrow">Root-cause file</p>
            <p className="mono mt-2 text-sm">{diagnosis.root_cause_file ?? "unresolved"}</p>
          </div>
          <div className="bg-[var(--graphite-900)] p-4">
            <p className="eyebrow">Service</p>
            <p className="mono mt-2 text-sm">{diagnosis.service_name}</p>
          </div>
        </div>
        <h3 className="eyebrow mt-8 mb-3">Remediation strategy</h3>
        <p className="text-sm leading-6 text-[var(--steel-300)]">{diagnosis.remediation_strategy}</p>
      </section>
      <aside className="space-y-6">
        <section className="panel p-5">
          <p className="eyebrow mb-4">Supporting evidence</p>
          <ul className="space-y-3">
            {diagnosis.supporting_metrics.map((metric) => (
              <li className="border-l border-[var(--cyan)] pl-3 text-xs leading-5 text-[var(--steel-300)]" key={metric}>
                {metric}
              </li>
            ))}
          </ul>
        </section>
        <section className="panel p-5">
          <p className="eyebrow mb-4">Rejected hypotheses</p>
          <ul className="space-y-2 text-xs leading-5 text-[var(--steel-500)]">
            {diagnosis.rejected_hypotheses.map((hypothesis) => (
              <li key={hypothesis}>— {hypothesis}</li>
            ))}
          </ul>
        </section>
      </aside>
    </div>
  );
}

function PatchView({ run }: { run: Run }) {
  if (!run.patch) {
    return (
      <div className="panel p-8">
        <p className="eyebrow mb-3">Forge idle</p>
        <h2 className="text-2xl font-medium">No governed patch is available.</h2>
        <p className="mt-4 text-sm text-[var(--steel-300)]">
          Patches are generated only after an evidence-backed regression diagnosis.
        </p>
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <section className="panel p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="eyebrow">Patch proposal</p>
            <p className="mt-2 text-sm text-[var(--steel-300)]">{run.patch.explanation}</p>
          </div>
          <StatusBadge
            label={run.patch_audit?.passed ? "AUDIT PASSED" : "AUDIT PENDING"}
            value={run.patch_audit?.passed ? "PASSED" : "ACTIVE"}
          />
        </div>
      </section>
      <section className="panel overflow-hidden">
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-3">
          <p className="eyebrow">Unified diff</p>
          <span className="mono text-[.64rem] text-[var(--steel-500)]">
            {run.patch.changed_files.length} FILE(S)
          </span>
        </div>
        <pre className="mono max-h-[640px] overflow-auto p-5 text-xs leading-5 text-[var(--steel-300)]">
          {run.patch.unified_diff}
        </pre>
      </section>
      <section className="panel">
        <div className="border-b border-white/10 px-5 py-4">
          <p className="eyebrow">Independent audit</p>
        </div>
        <ul className="divide-y divide-white/[.06]">
          {(run.patch_audit?.checks ?? []).map((check) => (
            <li className="grid gap-2 px-5 py-4 sm:grid-cols-[180px_1fr]" key={check.name}>
              <span className={`mono text-xs ${check.passed ? "text-[var(--green)]" : "text-[var(--red)]"}`}>
                {check.passed ? "PASS" : "FAIL"} · {check.name}
              </span>
              <span className="text-xs text-[var(--steel-300)]">{check.detail}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Elapsed({ run }: { run: Run }) {
  const [now, setNow] = useState(() => Date.now());
  const active = !run.terminal_state;
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(timer);
  }, [active]);
  const end = active ? now : new Date(run.updated_at).getTime();
  const seconds = Math.max(0, Math.floor((end - new Date(run.created_at).getTime()) / 1000));
  return (
    <span className="mono">
      {String(Math.floor(seconds / 60)).padStart(2, "0")}:{String(seconds % 60).padStart(2, "0")}
    </span>
  );
}

function Gate({ label, state }: { label: string; state: "pass" | "fail" | "active" | "pending" }) {
  const tone = {
    pass: "text-[var(--green)]",
    fail: "text-[var(--red)]",
    active: "text-[var(--ember)]",
    pending: "text-[var(--steel-500)]",
  }[state];
  const text = { pass: "PASS", fail: "FAIL", active: "RUNNING", pending: "PENDING" }[state];
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-xs text-[var(--steel-300)]">{label}</span>
      <span className={`mono text-[0.66rem] ${tone} ${state === "active" ? "live-pulse" : ""}`}>{text}</span>
    </div>
  );
}

function ExecutionGates({ run }: { run: Run }) {
  const phaseState = (phase: "baseline" | "candidate" | "patched") => {
    const experiment = run.experiments[phase];
    if (!experiment) return run.terminal_state ? "pending" : "active";
    return experiment.successful ? "pass" : "fail";
  };
  const mcpCalls = (["baseline", "candidate", "patched"] as const).reduce(
    (total, phase) => total + (run.telemetry[phase]?.mcp_invocations.length ?? 0),
    0,
  );
  return (
    <div className="border-t border-white/10 p-5 lg:border-t-0 lg:border-l">
      <p className="eyebrow mb-4">Execution gates</p>
      <div className="space-y-2.5">
        <Gate label="k6 baseline" state={phaseState("baseline")} />
        <Gate label="k6 candidate" state={phaseState("candidate")} />
        <Gate label="k6 patched rerun" state={phaseState("patched")} />
        <Gate
          label="Patch audit"
          state={run.patch_audit ? (run.patch_audit.passed ? "pass" : "fail") : "pending"}
        />
        <Gate
          label="Sandbox verification"
          state={
            run.verification
              ? run.verification.status === "VERIFIED_IMPROVEMENT" ||
                run.verification.status === "VERIFIED_NO_CHANGE"
                ? "pass"
                : "fail"
              : "pending"
          }
        />
      </div>
      <p className="mono mt-5 text-[0.62rem] text-[var(--steel-500)]">
        {mcpCalls} SIGNOZ MCP TOOL CALLS RECORDED
      </p>
    </div>
  );
}

function LiveView({ run, messages }: { run: Run; messages: string[] }) {
  const endpoint = run.load_plan?.endpoint;
  return (
    <div className="space-y-6">
      <section className="panel grid gap-px bg-white/10 md:grid-cols-4">
        <div className="bg-[var(--graphite-900)] p-5">
          <p className="eyebrow">Repository</p>
          <p className="mono mt-2 truncate text-xs text-[var(--steel-300)]" title={run.target.path}>
            {run.target.path}
          </p>
        </div>
        <div className="bg-[var(--graphite-900)] p-5">
          <p className="eyebrow">Change</p>
          <p className="mono mt-2 text-xs text-[var(--cyan)]">
            {run.target.base_ref} → {run.target.candidate_ref}
          </p>
        </div>
        <div className="bg-[var(--graphite-900)] p-5">
          <p className="eyebrow">Scoped operation</p>
          <p className="mono mt-2 text-xs">
            {endpoint ? `${endpoint.method} ${endpoint.path}` : "Discovering…"}
          </p>
        </div>
        <div className="bg-[var(--graphite-900)] p-5">
          <p className="eyebrow">Elapsed</p>
          <p className="mt-2 text-xs text-[var(--paper)]">
            <Elapsed run={run} />
          </p>
        </div>
      </section>
      <MetricComparison run={run} />
      <section className="panel">
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
          <div>
            <p className="eyebrow">Live execution</p>
            <h2 className="mt-1 text-lg font-medium">{run.stage.replaceAll("_", " ")}</h2>
          </div>
          <StatusBadge value={run.terminal_state ?? "ACTIVE"} />
        </div>
        <div className="grid lg:grid-cols-[1fr_300px_260px]">
          <div className="min-h-64 p-5">
            <p className="eyebrow mb-4">Run events</p>
            {messages.length === 0 ? (
              <p className="text-sm text-[var(--steel-500)]">Waiting for the next state transition…</p>
            ) : (
              <ol className="mono space-y-3 text-xs">
                {messages.slice(-12).map((message, index) => (
                  <li className="flex gap-3 text-[var(--steel-300)]" key={`${message}-${index}`}>
                    <span className="text-[var(--ember)]">›</span>
                    {message}
                  </li>
                ))}
              </ol>
            )}
          </div>
          <div className="border-t border-white/10 p-5 lg:border-t-0 lg:border-l">
            <p className="eyebrow mb-4">Telemetry ingestion</p>
            <div className="space-y-4">
              {(["baseline", "candidate", "patched"] as const).map((phase) => {
                const evidence = run.telemetry[phase];
                return (
                  <div className="flex items-center justify-between" key={phase}>
                    <span className="mono text-xs capitalize text-[var(--steel-300)]">{phase}</span>
                    <Availability
                      available={Boolean(evidence?.available)}
                      availableText="confirmed"
                      unavailableText={evidence ? "unavailable" : "pending"}
                    />
                  </div>
                );
              })}
            </div>
          </div>
          <ExecutionGates run={run} />
        </div>
      </section>
    </div>
  );
}

export function RunConsole({ runId, initialView = "live" }: { runId: string; initialView?: View }) {
  const [run, setRun] = useState<Run | null>(null);
  const [messages, setMessages] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const next = await getRun(runId);
      setRun(next);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Run could not be loaded");
    }
  }, [runId]);

  useEffect(() => {
    const initialRefresh = window.setTimeout(() => void refresh(), 0);
    const source = new EventSource(`${API_URL}/api/v1/runs/${encodeURIComponent(runId)}/events`);
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as { action?: string; next_state?: string; type?: string };
        setMessages((current) => [
          ...current.slice(-30),
          payload.action ? `${payload.action} → ${payload.next_state ?? "complete"}` : (payload.type ?? "event"),
        ]);
      } catch {
        setMessages((current) => [...current.slice(-30), "event received"]);
      }
      void refresh();
    };
    const named = ["state.transition", "telemetry.phase", "run.error", "run.created"];
    named.forEach((name) =>
      source.addEventListener(name, (event) => {
        const message = event as MessageEvent<string>;
        try {
          const payload = JSON.parse(message.data) as { action?: string; next_state?: string; error?: string };
          setMessages((current) => [
            ...current.slice(-30),
            payload.error ?? `${payload.action ?? name} ${payload.next_state ?? ""}`.trim(),
          ]);
        } catch {
          setMessages((current) => [...current.slice(-30), name]);
        }
        void refresh();
      }),
    );
    const timer = window.setInterval(() => void refresh(), 5_000);
    return () => {
      source.close();
      window.clearTimeout(initialRefresh);
      window.clearInterval(timer);
    };
  }, [refresh, runId]);

  const tabs = useMemo(
    () => [
      ["proof", "Release proof", `/runs/${runId}/proof`],
      ["live", "Live run", `/runs/${runId}`],
      ["evidence", "Evidence", `/runs/${runId}/evidence`],
      ["diagnosis", "Diagnosis", `/runs/${runId}/diagnosis`],
      ["patch", "Patch", `/runs/${runId}/patch`],
    ] as const,
    [runId],
  );

  if (error && !run) {
    return (
      <div className="panel border-l-2 border-l-[var(--red)] p-8" role="alert">
        <p className="eyebrow mb-3">Run unavailable</p>
        <p className="text-[var(--red)]">{error}</p>
        <button className="mono mt-5 cursor-pointer text-xs text-[var(--cyan)]" onClick={() => void refresh()}>
          RETRY
        </button>
      </div>
    );
  }
  if (!run) {
    return <div className="panel p-8 text-sm text-[var(--steel-300)]">Loading run recorder…</div>;
  }

  return (
    <div>
      <div className="mb-7 flex flex-wrap items-start justify-between gap-5">
        <div>
          <p className="eyebrow mb-2">Run / {run.run_id}</p>
          <h1 className="text-3xl font-semibold tracking-[-.025em]">Reliability experiment</h1>
          <p className="mono mt-2 text-xs text-[var(--steel-500)]">
            {new Date(run.created_at).toISOString()} · {run.target.profile.toUpperCase()} PROFILE
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Availability
            available={connected}
            availableText="live channel"
            unavailableText="polling fallback"
          />
          {!run.terminal_state && (
            <button
              className="mono cursor-pointer border border-white/20 px-3 py-2 text-[.66rem] text-[var(--steel-300)] hover:border-[var(--red)] hover:text-[var(--red)]"
              onClick={() => void cancelRun(run.run_id).then(setRun)}
            >
              CANCEL
            </button>
          )}
        </div>
      </div>
      <nav aria-label="Run views" className="mb-7 flex overflow-x-auto border-b border-white/10">
        {tabs.map(([view, label, href]) => (
          <Link
            aria-current={initialView === view ? "page" : undefined}
            className={`mono whitespace-nowrap border-b-2 px-4 py-3 text-[.68rem] font-semibold tracking-[.06em] ${
              initialView === view
                ? "border-[var(--ember)] text-[var(--paper)]"
                : "border-transparent text-[var(--steel-500)] hover:text-[var(--steel-300)]"
            }`}
            href={href}
            key={view}
          >
            {label.toUpperCase()}
          </Link>
        ))}
      </nav>
      {initialView === "live" && <LiveView messages={messages} run={run} />}
      {initialView === "evidence" && <EvidenceView run={run} />}
      {initialView === "diagnosis" && <DiagnosisView run={run} />}
      {initialView === "patch" && <PatchView run={run} />}
      {initialView === "proof" && <ReleaseProofView run={run} />}
    </div>
  );
}

export function RunAside({ runId }: { runId: string }) {
  const [run, setRun] = useState<Run | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    getRun(runId, controller.signal).then(setRun).catch(() => undefined);
    const timer = window.setInterval(() => getRun(runId).then(setRun).catch(() => undefined), 4_000);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [runId]);
  return (
    <div className="sticky top-8">
      <div className="mb-6">
        <p className="eyebrow mb-3">State machine</p>
        {run ? <Timeline run={run} /> : <p className="text-xs text-[var(--steel-500)]">Loading…</p>}
      </div>
      <div className="h-px ember-line" />
      <div className="mt-6">
        <p className="eyebrow mb-3">Audit chain</p>
        <Availability
          available={Boolean(run?.terminal_state)}
          availableText="terminal chain recorded"
          unavailableText="append-only recording"
        />
        <p className="mono mt-3 break-all text-[.62rem] leading-5 text-[var(--steel-500)]">
          {runId}
        </p>
      </div>
    </div>
  );
}

