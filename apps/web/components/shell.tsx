import type { ReactNode } from "react";

import { Brand } from "@/components/brand";

export function Shell({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-white/10 bg-[rgba(9,11,13,.88)] backdrop-blur-md">
        <div className="mx-auto flex max-w-[1480px] items-center justify-between px-5 py-4 lg:px-8">
          <Brand />
          <div className="mono flex items-center gap-3 text-[0.68rem] text-[var(--steel-300)]">
            <span className="hidden sm:inline">PRE-PRODUCTION RELIABILITY SYSTEM</span>
            <span className="h-4 w-px bg-white/15" />
            <span>v0.1.0</span>
          </div>
        </div>
      </header>
      <div className="mx-auto grid max-w-[1480px] lg:grid-cols-[minmax(0,1fr)_300px]">
        <main className="min-w-0 px-5 py-8 lg:px-8 lg:py-10" id="main-content">
          {children}
        </main>
        {aside && (
          <aside className="border-l border-white/10 px-5 py-8 lg:min-h-[calc(100vh-71px)] lg:px-6 lg:py-10">
            {aside}
          </aside>
        )}
      </div>
    </div>
  );
}

