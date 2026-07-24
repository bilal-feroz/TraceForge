import { RunAside, RunConsole } from "@/components/run-console";
import { Shell } from "@/components/shell";

type View = "live" | "evidence" | "diagnosis" | "patch" | "proof";

export function RunPage({ runId, view }: { runId: string; view: View }) {
  return (
    <Shell aside={<RunAside runId={runId} />}>
      <RunConsole initialView={view} runId={runId} />
    </Shell>
  );
}

