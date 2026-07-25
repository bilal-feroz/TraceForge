"use client";

import { useEffect, useMemo, useState } from "react";

import { Availability, StatusBadge } from "@/components/status";
import { API_URL, getReleaseProof } from "@/lib/api";
import type { ComparisonMetric, PhaseEvidence, PhaseName, ReleaseProof, Run } from "@/lib/types";

const PHASES: PhaseName[] = ["baseline", "candidate", "patched"];

const PHASE_CAPTION: Record<PhaseName, string> = {
  baseline: "Base revision under load",
  candidate: "Candidate revision under identical load",
  patched: "Patched candidate rerun in the sandbox",
};

type Tone = "neutral" | "cyan" | "green" | "red" | "amber";

const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-[var(--paper)]",
  cyan: "text-[var(--cyan)]",
  green: "text-[var(--green)]",
  red: "text-[var(--red)]",
  amber: "text-[var(--amber)]",
};

function num(value: number | null | undefined, digits = 2): string {
  return value === null || value === undefined || !Number.isFinite(value)
    ? "—"
    : value.toFixed(digits);
}

function integer(value: number | null | undefined): string {
  return value === null || value === undefined || !Number.isFinite(value)
    ? "—"
    : Math.round(value).toLocaleString("en-US");
}

function metricText(metric: ComparisonMetric, value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  if (metric.unit === "%") return `${value.toFixed(2)}%`;
  if (metric.unit === "ms") return `${value.toFixed(2)} ms`;
  if (metric.unit === "req/s") return `${value.toFixed(2)} req/s`;
  if (metric.unit === "in flight") return `${value.toFixed(1)} in flight`;
  return integer(value);
}

function relative(metric: ComparisonMetric, value: number | null | undefined): string {
  const base = metric.baseline;
  if (value === null || value === undefined || base === null || base === undefined) return "";
  if (base === value) return "no change vs baseline";
  if (base === 0) return `${value > 0 ? "+" : ""}${metricText(metric, value)} from zero baseline`;
  const change = ((value - base) / Math.abs(base)) * 100;
  return `${change > 0 ? "+" : ""}${change.toFixed(2)}% vs baseline`;
}

function cellTone(metric: ComparisonMetric, phase: PhaseName): Tone {
  const base = metric.baseline;
  const value = metric[phase];
  if (base === null || base === undefined || value === null || value === undefined) return "neutral";
  if (metric.caveat && phase === "candidate") return "amber";
  if (metric.direction === "neutral") return "neutral";
  const change = base === 0 ? (value === 0 ? 0 : Number.POSITIVE_INFINITY) : Math.abs((value - base) / base);
  if (change < 0.1) return "neutral";
  const worse = metric.direction === "lower_is_better" ? value > base : value < base;
  return worse ? "red" : "green";
}

function Section({
  index,
  title,
  caption,
  action,
  children,
}: {
  index: string;
  title: string;
  caption?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section aria-labelledby={`section-${index}`} className="panel">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-white/10 px-5 py-4">
        <div>
          <p className="eyebrow">{index} / TraceForge</p>
          <h2 className="mt-1 text-lg font-medium" id={`section-${index}`}>
            {title}
          </h2>
          {caption && <p className="mt-1 max-w-3xl text-xs leading-5 text-[var(--steel-500)]">{caption}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function Fact({ label, value, tone = "neutral", title }: { label: string; value: string; tone?: Tone; title?: string }) {
  return (
    <div className="bg-[var(--graphite-900)] p-4">
      <p className="eyebrow text-[0.6rem]">{label}</p>
      <p className={`mono mt-2 truncate text-xs ${TONE_TEXT[tone]}`} title={title ?? value}>
        {value}
      </p>
    </div>
  );
}

function signozOrigin(proof: ReleaseProof): string | null {
  for (const item of proof.phases) {
    for (const link of item.evidence?.trace_links ?? []) {
      if (!link.signoz_url) continue;
      try {
        return new URL(link.signoz_url).origin;
      } catch {
        return null;
      }
    }
  }
  return null;
}

function evidenceTone(status: ReleaseProof["evidence_status"]): Tone {
  if (status === "confirmed") return "cyan";
  if (status === "partial") return "amber";
  if (status === "unavailable") return "red";
  return "neutral";
}

function Overview({ proof }: { proof: ReleaseProof }) {
  const verdict = proof.verdict;
  const verdictTone: Tone =
    verdict === "SHIP" ? "green" : verdict === "BLOCK" ? "red" : verdict ? "amber" : "neutral";
  return (
    <section className="panel border-t-2 border-t-[var(--ember)]">
      <div className="flex flex-wrap items-start justify-between gap-6 p-6">
        <div className="min-w-0">
          <p className="eyebrow">Release proof</p>
          <div className="mt-3 flex flex-wrap items-center gap-4">
            <h1 className={`mono text-4xl font-semibold tracking-[-0.02em] ${TONE_TEXT[verdictTone]}`}>
              {verdict ?? "IN PROGRESS"}
            </h1>
            <StatusBadge
              label={proof.terminal_state ?? proof.stage.replaceAll("_", " ")}
              value={proof.terminal_state ?? "ACTIVE"}
            />
          </div>
          <p className="mt-4 max-w-3xl text-sm leading-6 text-[var(--steel-300)]">
            {proof.verdict_reason ?? "TraceForge has not published a verdict for this run yet."}
          </p>
        </div>
        <div className="space-y-2 text-right">
          <Availability
            available={proof.evidence_status === "confirmed"}
            availableText={`SigNoz evidence confirmed · ${proof.signoz_service ?? "service"}`}
            unavailableText={`SigNoz evidence ${proof.evidence_status}`}
          />
          <p className="mono text-[0.66rem] text-[var(--steel-500)]">
            {proof.ledger.valid ? "LEDGER VERIFIED" : "LEDGER NOT VERIFIED"} · {proof.ledger.event_count} EVENTS
          </p>
          <p className="mono text-[0.66rem] text-[var(--steel-500)]">
            {proof.patch_verification_status ?? "VERIFICATION PENDING"}
          </p>
        </div>
      </div>
      <div className="grid gap-px border-t border-white/10 bg-white/10 sm:grid-cols-2 lg:grid-cols-4">
        <Fact label="Run ID" value={proof.run_id} />
        <Fact label="Repository" value={proof.repository} />
        <Fact label="Endpoint" tone="cyan" value={proof.endpoint ?? "not scoped yet"} />
        <Fact label="Profile" value={`${proof.profile} · ${proof.scenario ?? "scenario pending"}`} />
        <Fact
          label="Base revision"
          value={`${proof.base_ref} · ${proof.base_sha?.slice(0, 12) ?? "unresolved"}`}
          title={proof.base_sha ?? undefined}
        />
        <Fact
          label="Candidate revision"
          value={`${proof.candidate_ref} · ${proof.candidate_sha?.slice(0, 12) ?? "unresolved"}`}
          title={proof.candidate_sha ?? undefined}
        />
        <Fact
          label="SigNoz evidence"
          tone={evidenceTone(proof.evidence_status)}
          value={proof.evidence_status}
        />
        <Fact
          label="Ledger"
          tone={proof.ledger.valid ? "green" : proof.ledger.recorded ? "red" : "neutral"}
          value={
            proof.ledger.recorded
              ? `${proof.ledger.valid ? "chain intact" : "chain broken"} · ${proof.ledger.head_hash_prefix ?? ""}`
              : "no ledger events"
          }
        />
        <Fact label="Created" value={new Date(proof.created_at).toISOString()} />
        <Fact label="Last update" value={new Date(proof.updated_at).toISOString()} />
        <Fact label="Wall clock" value={`${num(proof.elapsed_seconds, 1)} s`} />
        <Fact
          label="Classification"
          tone={proof.classification === "NO_REGRESSION" ? "green" : proof.classification ? "red" : "neutral"}
          value={proof.classification ?? "not classified"}
        />
      </div>
    </section>
  );
}

function Interpretation({ proof }: { proof: ReleaseProof }) {
  if (proof.interpretation.length === 0) return null;
  return (
    <section className="panel border-l-2 border-l-[var(--amber)] p-6" role="note">
      <p className="eyebrow">How to read these numbers</p>
      <ul className="mt-4 space-y-3">
        {proof.interpretation.map((note) => (
          <li className="flex gap-3 text-sm leading-6 text-[var(--steel-300)]" key={note}>
            <span aria-hidden="true" className="text-[var(--amber)]">
              ·
            </span>
            {note}
          </li>
        ))}
      </ul>
    </section>
  );
}

function ComparisonTable({ proof }: { proof: ReleaseProof }) {
  const available = new Set(proof.phases.filter((item) => item.load ?? item.evidence).map((item) => item.phase));
  return (
    <Section
      caption="Every phase ran the identical generated k6 script. Latency alone cannot settle a verdict, so the table pairs client timings with the correlated server-side counts."
      index="01"
      title="Three-phase comparison"
    >
      {available.size === 0 ? (
        <p className="p-6 text-sm text-[var(--steel-500)]">No experiment has completed for this run.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-left">
            <caption className="sr-only">Baseline, candidate, and patched measurements</caption>
            <thead className="eyebrow border-b border-white/10 text-[0.6rem]">
              <tr>
                <th className="px-5 py-3 font-medium" scope="col">
                  Measurement
                </th>
                {PHASES.map((phase) => (
                  <th className="px-5 py-3 text-right font-medium" key={phase} scope="col">
                    {phase}
                  </th>
                ))}
                <th className="px-5 py-3 font-medium" scope="col">
                  Reading
                </th>
              </tr>
            </thead>
            <tbody>
              {proof.comparison.map((metric) => (
                <tr className="border-b border-white/[.06] last:border-0" key={metric.key}>
                  <th className="px-5 py-3 text-sm font-normal text-[var(--steel-300)]" scope="row">
                    {metric.label}
                    <span className="mono ml-2 text-[0.6rem] text-[var(--steel-500)]">
                      {metric.direction === "lower_is_better"
                        ? "LOWER BETTER"
                        : metric.direction === "higher_is_better"
                          ? "HIGHER BETTER"
                          : "CONTEXT"}
                    </span>
                  </th>
                  {PHASES.map((phase) => (
                    <td
                      className={`mono px-5 py-3 text-right text-xs ${TONE_TEXT[cellTone(metric, phase)]}`}
                      key={phase}
                    >
                      {available.has(phase) ? metricText(metric, metric[phase]) : "not run"}
                    </td>
                  ))}
                  <td className="px-5 py-3 text-xs leading-5 text-[var(--steel-500)]">
                    {metric.caveat ? (
                      <span className="text-[var(--amber)]">{metric.caveat}</span>
                    ) : (
                      relative(metric, metric.candidate)
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function WindowTrend({ proof }: { proof: ReleaseProof }) {
  const series = proof.phases
    .map((item) => ({ phase: item.phase, values: item.load?.ordered_p95_windows_ms ?? [] }))
    .filter((item) => item.values.length > 0);
  if (series.length === 0) return null;
  const peak = Math.max(...series.flatMap((item) => item.values));
  return (
    <Section
      caption={`P95 per ordered load window on one shared scale (peak ${num(peak, 0)} ms). A rising shape is what separates a real trend from a single slow request.`}
      index="02"
      title="Latency trend across load windows"
    >
      <div className="grid gap-px bg-white/10 lg:grid-cols-3">
        {series.map((item) => (
          <div className="bg-[var(--graphite-900)] p-5" key={item.phase}>
            <p className="eyebrow text-[0.62rem]">{item.phase}</p>
            <div aria-hidden="true" className="mt-4 flex h-28 items-end gap-1.5">
              {item.values.map((value, index) => (
                <span
                  className={`flex-1 ${
                    item.phase === "candidate" ? "bg-[var(--ember)]/70" : "bg-[var(--cyan)]/50"
                  }`}
                  key={`${item.phase}-${index}`}
                  style={{ height: `${Math.max(2, (value / peak) * 100)}%` }}
                />
              ))}
            </div>
            <p className="mono mt-3 text-[0.62rem] leading-5 text-[var(--steel-500)]">
              {item.values.map((value) => num(value, 0)).join(" · ")} ms
            </p>
          </div>
        ))}
      </div>
    </Section>
  );
}

function Timeline({ proof }: { proof: ReleaseProof }) {
  return (
    <Section
      caption="Recorded from the hash-chained ledger, so the timeline is the audit trail rather than a rendered animation."
      index="03"
      title="Experiment timeline"
    >
      {proof.timeline.length === 0 ? (
        <p className="p-6 text-sm text-[var(--steel-500)]">No ledger events have been written yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left">
            <thead className="eyebrow border-b border-white/10 text-[0.6rem]">
              <tr>
                <th className="px-5 py-3 font-medium" scope="col">
                  #
                </th>
                <th className="px-5 py-3 font-medium" scope="col">
                  Action
                </th>
                <th className="px-5 py-3 font-medium" scope="col">
                  Transition
                </th>
                <th className="px-5 py-3 text-right font-medium" scope="col">
                  Elapsed
                </th>
                <th className="px-5 py-3 font-medium" scope="col">
                  Outcome
                </th>
                <th className="px-5 py-3 font-medium" scope="col">
                  Event hash
                </th>
              </tr>
            </thead>
            <tbody>
              {proof.timeline.map((event) => (
                <tr className="border-b border-white/[.06] last:border-0" key={event.sequence}>
                  <td className="mono px-5 py-2.5 text-[0.66rem] text-[var(--steel-500)]">{event.sequence}</td>
                  <td className="mono px-5 py-2.5 text-xs text-[var(--paper)]">{event.action}</td>
                  <td className="mono px-5 py-2.5 text-[0.66rem] text-[var(--steel-500)]">
                    {event.previous_state} → {event.next_state}
                  </td>
                  <td className="mono px-5 py-2.5 text-right text-[0.66rem] text-[var(--cyan)]">
                    {num(event.elapsed_seconds, 1)} s
                  </td>
                  <td
                    className={`mono px-5 py-2.5 text-[0.66rem] ${
                      event.outcome === "success" ? "text-[var(--green)]" : "text-[var(--red)]"
                    }`}
                  >
                    {event.outcome}
                  </td>
                  <td className="mono px-5 py-2.5 text-[0.66rem] text-[var(--steel-500)]">
                    {event.event_hash_prefix}…
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function Classification({ run, proof }: { run: Run; proof: ReleaseProof }) {
  const assessment = run.assessment;
  return (
    <Section
      caption="Fixed numeric gates decide the classification. No language model participates in this step."
      index="04"
      title="Deterministic regression classification"
    >
      {!assessment ? (
        <p className="p-6 text-sm text-[var(--steel-500)]">
          Classification runs after both load phases and the correlated telemetry gate.
        </p>
      ) : (
        <div className="grid gap-px bg-white/10 lg:grid-cols-2">
          <div className="bg-[var(--graphite-900)] p-5">
            <p className="eyebrow text-[0.62rem]">Result</p>
            <p
              className={`mono mt-3 text-xl ${
                proof.classification === "NO_REGRESSION" ? "text-[var(--green)]" : "text-[var(--red)]"
              }`}
            >
              {assessment.classification}
            </p>
            <ul className="mt-5 space-y-2 text-xs leading-5 text-[var(--steel-300)]">
              {assessment.deterministic_reasons.map((reason) => (
                <li key={reason}>— {reason}</li>
              ))}
            </ul>
            <p className="mono mt-5 text-[0.66rem] text-[var(--steel-500)]">
              SUFFICIENT EVIDENCE: {assessment.sufficient_evidence ? "YES" : "NO"}
            </p>
          </div>
          <div className="bg-[var(--graphite-900)] p-5">
            <p className="eyebrow text-[0.62rem]">Gate inputs</p>
            <dl className="mt-4 space-y-2 text-xs">
              {[
                ["P95 delta", `${num(assessment.latency_p95.absolute)} ms`],
                ["P99 delta", `${num(assessment.latency_p99.absolute)} ms`],
                ["Failure-rate delta", num(assessment.error_rate.absolute, 4)],
                ["Throughput delta", `${num(assessment.throughput.absolute)} req/s`],
                [
                  "Ordered-window slope",
                  assessment.latency_slope_ms_per_window === null ||
                  assessment.latency_slope_ms_per_window === undefined
                    ? "not computable"
                    : `${num(assessment.latency_slope_ms_per_window)} ms/window`,
                ],
                [
                  "Implied client concurrency",
                  assessment.implied_concurrency
                    ? `${num(assessment.implied_concurrency.baseline, 1)} → ${num(
                        assessment.implied_concurrency.candidate,
                        1,
                      )} in flight`
                    : "not computable",
                ],
              ].map(([label, value]) => (
                <div className="flex justify-between gap-4" key={label}>
                  <dt className="text-[var(--steel-500)]">{label}</dt>
                  <dd className="mono text-[var(--paper)]">{value}</dd>
                </div>
              ))}
            </dl>
            {assessment.threshold_violations.length > 0 && (
              <div className="mt-5">
                <p className="eyebrow text-[0.6rem]">k6 thresholds violated</p>
                <ul className="mono mt-2 space-y-1 text-[0.66rem] text-[var(--red)]">
                  {assessment.threshold_violations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </Section>
  );
}

function Diagnosis({ run }: { run: Run }) {
  const diagnosis = run.diagnosis;
  return (
    <Section
      caption="A diagnosis is only written when correlated server evidence exists for the exact experiment window."
      index="05"
      title="Root-cause diagnosis"
    >
      {!diagnosis ? (
        <p className="p-6 text-sm text-[var(--steel-500)]">
          No diagnosis was produced, which is the expected result when there is no regression or no confirmed evidence.
        </p>
      ) : (
        <div className="grid gap-px bg-white/10 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="bg-[var(--graphite-900)] p-5">
            <p className="text-lg leading-7">{diagnosis.likely_root_cause}</p>
            <div className="mt-5 grid gap-px bg-white/10 sm:grid-cols-2">
              <Fact label="Affected endpoint" tone="cyan" value={diagnosis.affected_endpoint} />
              <Fact label="Confidence" value={`${num(diagnosis.confidence * 100, 0)}%`} />
              <Fact label="Root-cause file" value={diagnosis.root_cause_file ?? "unresolved"} />
              <Fact label="Service" value={diagnosis.service_name} />
            </div>
            <p className="eyebrow mt-6 text-[0.6rem]">Remediation strategy</p>
            <p className="mt-2 text-sm leading-6 text-[var(--steel-300)]">{diagnosis.remediation_strategy}</p>
          </div>
          <div className="bg-[var(--graphite-900)] p-5">
            <p className="eyebrow text-[0.6rem]">Supporting measurements</p>
            <ul className="mt-3 space-y-2">
              {diagnosis.supporting_metrics.map((metric) => (
                <li className="border-l border-[var(--cyan)] pl-3 text-xs leading-5 text-[var(--steel-300)]" key={metric}>
                  {metric}
                </li>
              ))}
            </ul>
            <p className="eyebrow mt-6 text-[0.6rem]">Rejected hypotheses</p>
            <ul className="mt-3 space-y-1 text-xs leading-5 text-[var(--steel-500)]">
              {diagnosis.rejected_hypotheses.map((item) => (
                <li key={item}>— {item}</li>
              ))}
            </ul>
            <p className="eyebrow mt-6 text-[0.6rem]">MCP tools used</p>
            <ul className="mono mt-3 space-y-1 text-[0.62rem] text-[var(--cyan)]">
              {diagnosis.mcp_tools_used.map((tool) => (
                <li key={tool}>{tool}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </Section>
  );
}

function EvidenceCard({ evidence }: { evidence: PhaseEvidence }) {
  const rows: Array<[string, string, Tone]> = [
    ["Correlated spans in window", integer(evidence.spans_in_window), "neutral"],
    [
      "Error spans",
      integer(evidence.error_spans_in_window),
      evidence.error_spans_in_window > 0 ? "red" : "neutral",
    ],
    ["Log records in window", integer(evidence.logs_in_window), "neutral"],
    [
      "Error logs",
      integer(evidence.error_logs_in_window),
      evidence.error_logs_in_window > 0 ? "red" : "neutral",
    ],
    [
      "`database is locked` logs",
      integer(evidence.lock_error_logs_in_window),
      evidence.lock_error_logs_in_window > 0 ? "red" : "neutral",
    ],
    ["Metric series returned", integer(evidence.metric_series), evidence.metric_series > 0 ? "cyan" : "amber"],
    ["MCP tool calls", integer(evidence.mcp_tool_calls), "cyan"],
    [
      "MCP tool failures",
      integer(evidence.mcp_tool_failures),
      evidence.mcp_tool_failures > 0 ? "red" : "neutral",
    ],
  ];
  return (
    <div className="bg-[var(--graphite-900)] p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="eyebrow text-[0.62rem]">{evidence.phase}</p>
        <Availability
          available={evidence.available}
          availableText="confirmed"
          unavailableText="unavailable"
        />
      </div>
      <p className="mt-2 text-[0.7rem] leading-4 text-[var(--steel-500)]">
        {PHASE_CAPTION[evidence.phase]}
      </p>
      <p className="mono mt-3 text-[0.62rem] leading-5 text-[var(--steel-500)]">
        {new Date(evidence.window.started_at).toISOString()}
        <br />→ {new Date(evidence.window.ended_at).toISOString()}
      </p>
      {!evidence.available && evidence.unavailable_reason && (
        <p className="mt-3 text-xs leading-5 text-[var(--amber)]">{evidence.unavailable_reason}</p>
      )}
      <dl className="mt-4 space-y-2 text-xs">
        {rows.map(([label, value, tone]) => (
          <div className="flex items-baseline justify-between gap-3" key={label}>
            <dt className="text-[var(--steel-500)]">{label}</dt>
            <dd className={`mono ${TONE_TEXT[tone]}`}>{value}</dd>
          </div>
        ))}
      </dl>
      {Object.keys(evidence.http_status_counts).length > 0 && (
        <div className="mt-4">
          <p className="eyebrow text-[0.58rem]">HTTP status distribution</p>
          <ul className="mono mt-2 flex flex-wrap gap-2 text-[0.62rem]">
            {Object.entries(evidence.http_status_counts).map(([code, count]) => (
              <li
                className={`border px-2 py-1 ${
                  code.startsWith("5") || code.startsWith("4")
                    ? "border-[rgba(255,92,97,.35)] text-[var(--red)]"
                    : "border-white/15 text-[var(--steel-300)]"
                }`}
                key={code}
              >
                {code} · {count}
              </li>
            ))}
          </ul>
        </div>
      )}
      {evidence.top_operations.length > 0 && (
        <div className="mt-4">
          <p className="eyebrow text-[0.58rem]">Slowest operations (span p95)</p>
          <ul className="mt-2 space-y-1 text-[0.66rem]">
            {evidence.top_operations.map((operation) => (
              <li className="flex justify-between gap-3" key={operation.operation}>
                <span className="mono truncate text-[var(--steel-300)]">{operation.operation}</span>
                <span className="mono text-[var(--cyan)]">
                  {num(operation.p95_ms)} ms · {operation.span_count}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="mono mt-4 text-[0.58rem] leading-4 text-[var(--steel-500)]">
        RETRIEVED {evidence.trace_rows_retrieved} SPAN ROWS / {evidence.log_rows_retrieved} LOG ROWS
        {evidence.row_limit_reached ? ` · ROW LIMIT ${evidence.row_limit} REACHED` : ""} ·{" "}
        {evidence.tools_discovered} TOOLS DISCOVERED
      </p>
    </div>
  );
}

function EvidenceSection({ proof }: { proof: ReleaseProof }) {
  const cards = proof.phases.map((item) => item.evidence).filter((item): item is PhaseEvidence => Boolean(item));
  return (
    <Section
      caption="Retrieved live through the official SigNoz MCP server and re-attributed to the exact phase window. Queries add a small ingestion margin, so these counts can be lower than the raw row counts."
      index="06"
      title="SigNoz evidence per phase"
    >
      {cards.length === 0 ? (
        <p className="p-6 text-sm text-[var(--steel-500)]">
          No telemetry has been retrieved for this run yet.
        </p>
      ) : (
        <div className="grid gap-px bg-white/10 lg:grid-cols-3">
          {cards.map((evidence) => (
            <EvidenceCard evidence={evidence} key={evidence.phase} />
          ))}
        </div>
      )}
    </Section>
  );
}

function TraceSection({ proof }: { proof: ReleaseProof }) {
  const [phase, setPhase] = useState<PhaseName>("candidate");
  const byPhase = useMemo(() => {
    const map = new Map<PhaseName, PhaseEvidence>();
    proof.phases.forEach((item) => {
      if (item.evidence) map.set(item.phase, item.evidence);
    });
    return map;
  }, [proof]);
  const options = PHASES.filter((item) => byPhase.has(item));
  const active = byPhase.get(phase) ?? (options[0] ? byPhase.get(options[0]) : undefined);
  return (
    <Section
      action={
        options.length > 0 ? (
          <div className="flex border border-white/15">
            {options.map((option) => (
              <button
                aria-pressed={active?.phase === option}
                className={`mono cursor-pointer px-3 py-2 text-[0.62rem] tracking-[.08em] ${
                  active?.phase === option
                    ? "bg-[var(--graphite-700)] text-[var(--paper)]"
                    : "text-[var(--steel-500)] hover:text-[var(--steel-300)]"
                }`}
                key={option}
                onClick={() => setPhase(option)}
                type="button"
              >
                {option.toUpperCase()}
              </button>
            ))}
          </div>
        ) : undefined
      }
      caption="Error spans are listed first. Links open the exact trace in SigNoz and are used only when SigNoz returned one."
      index="07"
      title="Correlated trace IDs"
    >
      {!active || active.trace_links.length === 0 ? (
        <p className="p-6 text-sm text-[var(--steel-500)]">No correlated spans are available for this phase.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left">
            <thead className="eyebrow border-b border-white/10 text-[0.6rem]">
              <tr>
                <th className="px-5 py-3 font-medium" scope="col">
                  Operation
                </th>
                <th className="px-5 py-3 text-right font-medium" scope="col">
                  Duration
                </th>
                <th className="px-5 py-3 font-medium" scope="col">
                  Status
                </th>
                <th className="px-5 py-3 font-medium" scope="col">
                  Trace ID
                </th>
                <th className="px-5 py-3 font-medium" scope="col">
                  SigNoz
                </th>
              </tr>
            </thead>
            <tbody>
              {active.trace_links.map((link) => (
                <tr className="border-b border-white/[.06] last:border-0" key={`${link.trace_id}-${link.span_id}`}>
                  <td className="px-5 py-2.5 text-xs">{link.operation}</td>
                  <td className="mono px-5 py-2.5 text-right text-xs text-[var(--cyan)]">
                    {num(link.duration_ms)} ms
                  </td>
                  <td
                    className={`mono px-5 py-2.5 text-xs ${
                      link.error ? "text-[var(--red)]" : "text-[var(--steel-300)]"
                    }`}
                  >
                    {link.status}
                  </td>
                  <td className="mono px-5 py-2.5 text-[0.66rem] break-all text-[var(--steel-500)]">
                    {link.trace_id}
                  </td>
                  <td className="px-5 py-2.5">
                    {link.signoz_url ? (
                      <a
                        className="mono text-[0.64rem] text-[var(--cyan)] underline-offset-4 hover:underline"
                        href={link.signoz_url}
                        rel="noreferrer noopener"
                        target="_blank"
                      >
                        OPEN TRACE
                      </a>
                    ) : (
                      <span className="mono text-[0.64rem] text-[var(--steel-500)]">no link returned</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function LogSection({ proof }: { proof: ReleaseProof }) {
  const candidate = proof.phases.find((item) => item.phase === "candidate")?.evidence;
  const samples = candidate?.log_samples ?? [];
  return (
    <Section
      caption="Candidate-phase log records carrying the exact run-ID attribute. Lock failures are marked."
      index="08"
      title="Correlated logs"
    >
      {samples.length === 0 ? (
        <p className="p-6 text-sm text-[var(--steel-500)]">No correlated log records are available.</p>
      ) : (
        <ul className="divide-y divide-white/[.06]">
          {samples.map((sample, index) => (
            <li className="grid gap-2 px-5 py-3 lg:grid-cols-[150px_110px_1fr]" key={`${sample.timestamp}-${index}`}>
              <span className="mono text-[0.62rem] text-[var(--steel-500)]">
                {new Date(sample.timestamp).toISOString().slice(11, 23)}
              </span>
              <span
                className={`mono text-[0.62rem] ${
                  sample.lock_error
                    ? "text-[var(--red)]"
                    : sample.severity.toUpperCase() === "ERROR"
                      ? "text-[var(--amber)]"
                      : "text-[var(--steel-500)]"
                }`}
              >
                {sample.severity}
                {sample.lock_error ? " · LOCK" : ""}
              </span>
              <span className="mono text-[0.68rem] leading-5 break-all text-[var(--steel-300)]">
                {sample.message}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function PatchSection({ run, proof }: { run: Run; proof: ReleaseProof }) {
  return (
    <Section
      action={
        run.patch_audit ? (
          <StatusBadge
            label={run.patch_audit.passed ? "AUDIT PASSED" : "AUDIT FAILED"}
            value={run.patch_audit.passed ? "PASSED" : "BLOCKED"}
          />
        ) : undefined
      }
      caption="Patches are limited to files named by the diagnosis, then audited by separate deterministic checks before any sandbox run."
      index="09"
      title="Generated patch and independent audit"
    >
      {!run.patch ? (
        <p className="p-6 text-sm text-[var(--steel-500)]">
          No patch was generated for this run.
        </p>
      ) : (
        <div>
          <div className="border-b border-white/10 px-5 py-4">
            <p className="text-sm leading-6 text-[var(--steel-300)]">{run.patch.explanation}</p>
            <p className="mono mt-2 text-[0.62rem] text-[var(--steel-500)]">
              {proof.patch_changed_files.join(", ") || "no files"}
            </p>
          </div>
          <pre className="mono max-h-[420px] overflow-auto border-b border-white/10 p-5 text-[0.7rem] leading-5 text-[var(--steel-300)]">
            {run.patch.unified_diff}
          </pre>
          <ul className="divide-y divide-white/[.06]">
            {(run.patch_audit?.checks ?? []).map((check) => (
              <li className="grid gap-2 px-5 py-3 sm:grid-cols-[210px_1fr]" key={check.name}>
                <span className={`mono text-xs ${check.passed ? "text-[var(--green)]" : "text-[var(--red)]"}`}>
                  {check.passed ? "PASS" : "FAIL"} · {check.name}
                </span>
                <span className="text-xs leading-5 text-[var(--steel-300)]">{check.detail}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Section>
  );
}

function SandboxSection({ run, proof }: { run: Run; proof: ReleaseProof }) {
  const verification = run.verification;
  const gates: Array<[string, boolean | undefined]> = [
    ["Sandbox tests passed", verification?.tests_passed],
    ["Patched telemetry confirmed", verification?.telemetry_complete],
    ["Identical k6 script digest", verification?.same_script_digest],
  ];
  return (
    <Section
      caption="The patch is applied only inside a managed Git worktree, then the identical experiment is replayed before any verdict."
      index="10"
      title="Sandbox verification"
    >
      {!verification ? (
        <p className="p-6 text-sm text-[var(--steel-500)]">Sandbox verification has not run.</p>
      ) : (
        <div className="grid gap-px bg-white/10 lg:grid-cols-2">
          <div className="bg-[var(--graphite-900)] p-5">
            <p className="eyebrow text-[0.62rem]">Verification status</p>
            <p
              className={`mono mt-3 text-lg ${
                proof.patch_verification_status === "VERIFIED_IMPROVEMENT"
                  ? "text-[var(--green)]"
                  : proof.patch_verification_status?.startsWith("VERIFIED_REGRESSION") ||
                      proof.patch_verification_status === "TESTS_FAILED"
                    ? "text-[var(--red)]"
                    : "text-[var(--amber)]"
              }`}
            >
              {verification.status}
            </p>
            <ul className="mt-5 space-y-2 text-xs">
              {gates.map(([label, passed]) => (
                <li className="flex items-center justify-between gap-3" key={label}>
                  <span className="text-[var(--steel-500)]">{label}</span>
                  <span className={`mono ${passed ? "text-[var(--green)]" : "text-[var(--steel-500)]"}`}>
                    {passed ? "PASS" : "NOT PROVEN"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="bg-[var(--graphite-900)] p-5">
            <p className="eyebrow text-[0.62rem]">Remaining risks</p>
            {verification.remaining_risks.length === 0 ? (
              <p className="mt-3 text-xs text-[var(--steel-500)]">No remaining risk was recorded.</p>
            ) : (
              <ul className="mt-3 space-y-2 text-xs leading-5 text-[var(--amber)]">
                {verification.remaining_risks.map((risk) => (
                  <li key={risk}>— {risk}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </Section>
  );
}

function LedgerSection({ proof }: { proof: ReleaseProof }) {
  const ledger = proof.ledger;
  return (
    <Section
      caption="Every transition is appended with a SHA-256 chain over the previous event. Re-verification is run on request, not cached from the run."
      index="11"
      title="Ledger verification"
    >
      <div className="grid gap-px bg-white/10 sm:grid-cols-2 lg:grid-cols-4">
        <Fact
          label="Chain"
          tone={ledger.valid ? "green" : ledger.recorded ? "red" : "neutral"}
          value={ledger.valid ? "verified" : ledger.recorded ? "verification failed" : "not recorded"}
        />
        <Fact label="Events" value={integer(ledger.event_count)} />
        <Fact label="Terminal state in chain" value={ledger.terminal_state ?? "none recorded"} />
        <Fact label="Head hash" value={ledger.head_hash_prefix ? `${ledger.head_hash_prefix}…` : "—"} />
      </div>
      {ledger.errors.length > 0 && (
        <ul className="mono space-y-1 px-5 py-4 text-[0.66rem] text-[var(--red)]">
          {ledger.errors.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      )}
      {!ledger.terminal_required && (
        <p className="px-5 py-4 text-xs text-[var(--steel-500)]">
          This run has not reached a terminal state, so the chain is verified without requiring a terminal event.
        </p>
      )}
    </Section>
  );
}

function LimitationsSection({ proof }: { proof: ReleaseProof }) {
  if (proof.limitations.length === 0) return null;
  return (
    <Section
      caption="Stated so a reviewer can judge how far these numbers generalize."
      index="12"
      title="Limitations of this run"
    >
      <ul className="space-y-3 p-5 text-xs leading-5 text-[var(--steel-500)]">
        {proof.limitations.map((item) => (
          <li key={item}>— {item}</li>
        ))}
      </ul>
    </Section>
  );
}

export function ReleaseProofView({ run }: { run: Run }) {
  const [proof, setProof] = useState<ReleaseProof | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getReleaseProof(run.run_id, controller.signal)
      .then((next) => {
        setProof(next);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : "Release proof could not be loaded");
      });
    return () => controller.abort();
  }, [run.run_id, run.stage, run.terminal_state, run.updated_at]);

  if (error && !proof) {
    return (
      <div className="panel border-l-2 border-l-[var(--red)] p-8" role="alert">
        <p className="eyebrow mb-3">Release proof unavailable</p>
        <p className="text-sm text-[var(--red)]">{error}</p>
      </div>
    );
  }
  if (!proof) {
    return (
      <div className="panel p-8 text-sm text-[var(--steel-300)]" role="status">
        Loading release proof…
      </div>
    );
  }

  const origin = signozOrigin(proof);

  return (
    <div className="space-y-6">
      <Overview proof={proof} />
      <Interpretation proof={proof} />
      <ComparisonTable proof={proof} />
      <WindowTrend proof={proof} />
      <Timeline proof={proof} />
      <Classification proof={proof} run={run} />
      <Diagnosis run={run} />
      <EvidenceSection proof={proof} />
      <TraceSection proof={proof} />
      <LogSection proof={proof} />
      <PatchSection proof={proof} run={run} />
      <SandboxSection proof={proof} run={run} />
      <LedgerSection proof={proof} />
      <LimitationsSection proof={proof} />
      <div className="flex flex-wrap gap-3">
        {origin && proof.signoz_service && (
          <a
            className="mono inline-flex border border-[var(--cyan)]/40 px-4 py-3 text-xs text-[var(--cyan)] hover:border-[var(--cyan)]"
            href={`${origin}/services/${encodeURIComponent(proof.signoz_service)}`}
            rel="noreferrer noopener"
            target="_blank"
          >
            OPEN SERVICE IN SIGNOZ
          </a>
        )}
        <a
          className="mono inline-flex border border-white/20 px-4 py-3 text-xs text-[var(--paper)] hover:border-[var(--cyan)]"
          href={`${API_URL}/api/v1/runs/${run.run_id}/report`}
        >
          DOWNLOAD EVIDENCE REPORT
        </a>
        <a
          className="mono inline-flex border border-white/20 px-4 py-3 text-xs text-[var(--paper)] hover:border-[var(--cyan)]"
          href={`${API_URL}/api/v1/runs/${run.run_id}/release-proof`}
        >
          RAW RELEASE-PROOF JSON
        </a>
      </div>
    </div>
  );
}
