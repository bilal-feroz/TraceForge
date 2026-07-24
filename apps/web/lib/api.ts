import type { Run } from "@/lib/types";

export const API_URL =
  process.env.NEXT_PUBLIC_TRACEFORGE_API_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8787";

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `TraceForge API returned ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function listRuns(signal?: AbortSignal): Promise<Run[]> {
  return parse<Run[]>(
    await fetch(`${API_URL}/api/v1/runs`, {
      cache: "no-store",
      signal,
    }),
  );
}

export async function getRun(runId: string, signal?: AbortSignal): Promise<Run> {
  return parse<Run>(
    await fetch(`${API_URL}/api/v1/runs/${encodeURIComponent(runId)}`, {
      cache: "no-store",
      signal,
    }),
  );
}

export async function createRun(input: {
  repository: string;
  base_ref: string;
  candidate_ref: string;
  target_url: string;
  profile: string;
}): Promise<Run> {
  return parse<Run>(
    await fetch(`${API_URL}/api/v1/runs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function cancelRun(runId: string): Promise<Run> {
  return parse<Run>(
    await fetch(`${API_URL}/api/v1/runs/${encodeURIComponent(runId)}/cancel`, {
      method: "POST",
    }),
  );
}

