import { RunPage } from "@/components/run-page";

export default async function Page({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  return <RunPage runId={runId} view="diagnosis" />;
}

