import Link from "next/link";

import { Shell } from "@/components/shell";

export default function NotFound() {
  return (
    <Shell>
      <div className="panel max-w-2xl p-8">
        <p className="eyebrow mb-3">Recorder / 404</p>
        <h1 className="text-3xl font-semibold">That run view does not exist.</h1>
        <Link className="mono mt-6 inline-block text-xs text-[var(--cyan)]" href="/">
          RETURN TO CONTROL ROOM
        </Link>
      </div>
    </Shell>
  );
}

