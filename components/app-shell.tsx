'use client'

import type { ReactNode } from 'react'
import { BottomNav } from '@/components/bottom-nav'
import { Sidebar } from '@/components/sidebar'
import { Radio } from 'lucide-react'

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative flex min-h-dvh w-full justify-center overflow-x-hidden bg-[#08030f]">
      {/* Ambient Cyber Lighting Blobs */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-40 left-1/3 h-[600px] w-[600px] rounded-full bg-violet-600/15 blur-[160px]" />
        <div className="absolute top-[30%] -right-40 h-[500px] w-[500px] rounded-full bg-fuchsia-600/10 blur-[160px]" />
        <div className="absolute bottom-0 left-10 h-[500px] w-[500px] rounded-full bg-indigo-600/10 blur-[160px]" />
      </div>

      {/* Unclamped Responsive Cyber HUD Layout (max-w-7xl) */}
      <div className="relative z-10 flex min-h-dvh w-full max-w-7xl border-x border-violet-900/20 bg-transparent shadow-2xl">
        {/* Desktop Sidebar (hidden on mobile, visible md+) */}
        <Sidebar />

        {/* Main Content Area */}
        <div className="flex min-w-0 flex-1 flex-col overflow-y-auto">
          {/* Cyber HUD Header with Live Telemetry Status Badge */}
          <header className="sticky top-0 z-20 flex items-center justify-between border-b border-violet-900/30 bg-[#08030f]/80 px-6 py-3.5 backdrop-blur-xl">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 font-mono text-xs text-purple-200/80">
                <span className="flex size-6 items-center justify-center rounded-lg bg-fuchsia-500/10 text-fuchsia-400">
                  <Radio className="size-3.5 animate-pulse" />
                </span>
                <span className="font-bold text-white">SMART STORAGE HUD</span>
                <span className="text-purple-400/40">/</span>
                <span className="text-violet-300">TELEMETRY GRID</span>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Live WebSocket Connection Status Badge */}
              <div
                data-testid="ws-status"
                className="ws-connected live-badge flex items-center gap-2 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 font-mono text-xs font-semibold text-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.25)]"
              >
                <span className="size-2 rounded-full bg-emerald-500 shadow-[0_0_8px_#10b981] animate-pulse" />
                <span>LIVE · ONLINE</span>
              </div>
            </div>
          </header>

          {/* Page Contents */}
          <main className="flex-1 pb-20 md:pb-8">
            {children}
          </main>

          {/* Mobile Bottom Navigation (hidden on desktop) */}
          <div className="md:hidden">
            <BottomNav />
          </div>
        </div>
      </div>
    </div>
  )
}

export function ScreenHeader({
  title,
  action,
}: {
  title: string
  action?: ReactNode
}) {
  return (
    <header className="flex items-center justify-between px-6 pb-4 pt-6">
      <h1 className="text-2xl font-bold tracking-tight text-white font-mono">
        {title}
      </h1>
      {action}
    </header>
  )
}