"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { Availability, StatusBadge } from "@/components/status";
import { API_URL, createRun, listRuns } from "@/lib/api";
import type { Run } from "@/lib/types";

const defaultForm = {
  repository: "",
  base_ref: "demo-baseline",
  candidate_ref: "demo-lock",
  target_url: "http://127.0.0.1:8099",
  profile: "demo",
};

function elapsed(date: string) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(date).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

export function ControlRoom() {
  const [form, setForm] = useState(defaultForm);
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [signozAvailable, setSignozAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      listRuns(controller.signal),
      fetch(`${API_URL}/api/v1/integrations/signoz/status`, {
        signal: controller.signal,
      })
        .then((response) => response.json() as Promise<{ available: boolean }>)
        .catch(() => ({ available: false })),
    ])
      .then(([items, signoz]) => {
        setRuns(items);
        setSignozAvailable(signoz.available);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "TraceForge API is unavailable");
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const run = await createRun(form);
      window.location.assign(`/runs/${run.run_id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Run could not be created");
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="mb-10 grid gap-8 xl:grid-cols-[minmax(0,1fr)_360px] xl:items-end">
        <div>
          <p className="eyebrow mb-4">Control Room / New experiment</p>
          <h1 className="max-w-4xl text-4xl leading-[1.05] font-semibold tracking-[-0.035em] sm:text-6xl">
            Put the change under load.
            <span className="block text-[var(--steel-500)]">Prove what the server saw.</span>
          </h1>
        </div>
        <div className="panel-inset border-l-2 border-l-[var(--cyan)] p-5">
          <p className="eyebrow mb-3">Evidence gate</p>
          {signozAvailable === null ? (
            <span className="mono text-xs text-[var(--steel-300)]">Checking SigNoz…</span>
          ) : (
            <Availability
              available={signozAvailable}
              availableText="SigNoz MCP connected"
              unavailableText="SigNoz verification unavailable"
            />
          )}
          <p className="mt-3 text-sm leading-6 text-[var(--steel-300)]">
            No server-side evidence means no telemetry-backed SHIP verdict.
          </p>
        </div>
      </div>

      <section aria-labelledby="intake-title" className="panel mb-10">
        <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
          <div>
            <p className="eyebrow">01 / Intake</p>
            <h2 className="mt-1 text-lg font-medium" id="intake-title">
              Experiment configuration
            </h2>
          </div>
          <span className="mono hidden text-[0.68rem] text-[var(--steel-500)] sm:block">
            LOCAL TARGETS ONLY BY DEFAULT
          </span>
        </div>
        <form className="grid gap-5 p-6 lg:grid-cols-2" onSubmit={submit}>
          <label className="lg:col-span-2">
            <span className="eyebrow mb-2 block">Repository root</span>
            <input
              className="w-full border border-white/15 bg-black/30 px-4 py-3 text-sm text-[var(--paper)] placeholder:text-[var(--steel-500)]"
              onChange={(event) => setForm({ ...form, repository: event.target.value })}
              placeholder="C:\work\service or /work/service"
              required
              value={form.repository}
            />
          </label>
          <label>
            <span className="eyebrow mb-2 block">Base ref</span>
            <input
              className="mono w-full border border-white/15 bg-black/30 px-4 py-3 text-sm"
              onChange={(event) => setForm({ ...form, base_ref: event.target.value })}
              required
              value={form.base_ref}
            />
          </label>
          <label>
            <span className="eyebrow mb-2 block">Candidate ref</span>
            <input
              className="mono w-full border border-white/15 bg-black/30 px-4 py-3 text-sm"
              onChange={(event) => setForm({ ...form, candidate_ref: event.target.value })}
              required
              value={form.candidate_ref}
            />
          </label>
          <label>
            <span className="eyebrow mb-2 block">Target URL</span>
            <input
              className="mono w-full border border-white/15 bg-black/30 px-4 py-3 text-sm"
              onChange={(event) => setForm({ ...form, target_url: event.target.value })}
              required
              type="url"
              value={form.target_url}
            />
          </label>
          <label>
            <span className="eyebrow mb-2 block">Load profile</span>
            <select
              className="mono w-full border border-white/15 bg-[var(--graphite-900)] px-4 py-3 text-sm"
              onChange={(event) => setForm({ ...form, profile: event.target.value })}
              value={form.profile}
            >
              <option value="quick">Quick · under 30 seconds</option>
              <option value="demo">Demo · staged, under 90 seconds</option>
              <option value="full">Full · explicitly configured</option>
            </select>
          </label>
          {error && (
            <div
              className="border border-[rgba(255,92,97,.35)] bg-[rgba(255,92,97,.08)] p-4 text-sm text-[var(--red)] lg:col-span-2"
              role="alert"
            >
              {error}
            </div>
          )}
          <div className="flex flex-col gap-4 border-t border-white/10 pt-5 sm:flex-row sm:items-center sm:justify-between lg:col-span-2">
            <p className="max-w-2xl text-xs leading-5 text-[var(--steel-500)]">
              The public API never accepts a shell command. Start the target separately or use the
              trusted-local CLI demo for worktree lifecycle automation.
            </p>
            <button
              className="mono min-w-48 cursor-pointer border border-[var(--ember)] bg-[var(--ember)] px-6 py-3 text-xs font-bold tracking-[.1em] text-black disabled:cursor-wait disabled:opacity-60"
              disabled={submitting}
              type="submit"
            >
              {submitting ? "IGNITING…" : "START RUN"}
            </button>
          </div>
        </form>
      </section>

      <section aria-labelledby="recent-title">
        <div className="mb-4 flex items-end justify-between">
          <div>
            <p className="eyebrow">Flight recorder</p>
            <h2 className="mt-1 text-xl font-medium" id="recent-title">
              Recent runs
            </h2>
          </div>
          <span className="mono text-[0.68rem] text-[var(--steel-500)]">
            {runs.length} RECORDED
          </span>
        </div>
        <div className="panel overflow-x-auto">
          {loading ? (
            <div className="p-8 text-sm text-[var(--steel-300)]">Loading recorded runs…</div>
          ) : runs.length === 0 ? (
            <div className="p-8">
              <p className="text-sm text-[var(--steel-300)]">No experiments recorded yet.</p>
              <p className="mt-2 text-xs text-[var(--steel-500)]">
                Configure a repository above or run <span className="mono">traceforge demo lock</span>.
              </p>
            </div>
          ) : (
            <table className="w-full min-w-[760px] border-collapse text-left">
              <thead className="eyebrow border-b border-white/10 text-[0.62rem]">
                <tr>
                  <th className="px-5 py-3 font-medium">Run</th>
                  <th className="px-5 py-3 font-medium">Change</th>
                  <th className="px-5 py-3 font-medium">Stage</th>
                  <th className="px-5 py-3 font-medium">Verdict</th>
                  <th className="px-5 py-3 font-medium">Updated</th>
                </tr>
              </thead>
              <tbody>
                {runs.slice(0, 12).map((run) => (
                  <tr className="border-b border-white/[.07] last:border-0" key={run.run_id}>
                    <td className="px-5 py-4">
                      <Link
                        className="mono text-xs text-[var(--cyan)] underline-offset-4 hover:underline"
                        href={`/runs/${run.run_id}`}
                      >
                        {run.run_id.slice(0, 8)}
                      </Link>
                    </td>
                    <td className="mono max-w-64 truncate px-5 py-4 text-xs text-[var(--steel-300)]">
                      {run.target.base_ref} → {run.target.candidate_ref}
                    </td>
                    <td className="mono px-5 py-4 text-[0.68rem] text-[var(--steel-300)]">
                      {run.stage.replaceAll("_", " ")}
                    </td>
                    <td className="px-5 py-4">
                      <StatusBadge
                        value={run.terminal_state ?? "ACTIVE"}
                        label={run.verdict?.value ?? (run.terminal_state ? undefined : "ACTIVE")}
                      />
                    </td>
                    <td className="mono px-5 py-4 text-[0.68rem] text-[var(--steel-500)]">
                      {elapsed(run.updated_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}

