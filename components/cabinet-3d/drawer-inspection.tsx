'use client'

import React from 'react'
import { X, MapPin, Zap, CheckCircle2, AlertTriangle, ShieldAlert } from 'lucide-react'

export interface DrawerSlotInfo {
  id: string
  slotNumber: string
  partNumber: string
  batchId: string
  shelfLife: string
  remaining: string
  degradation: string
  quantity: number
  temperature: string
  humidity: string
  status: 'OPTIMAL' | 'APPROACHING_LIMIT' | 'EXPIRED'
  isLocated?: boolean
}

interface DrawerInspectionProps {
  slot: DrawerSlotInfo | null
  onClose: () => void
  onLocate: (slotId: string) => void
  onDispatch?: (slotId: string, amount: number) => void
}

export function DrawerInspection({ slot, onClose, onLocate, onDispatch }: DrawerInspectionProps) {
  if (!slot) return null

  const isAlert = slot.status === 'EXPIRED'
  const isWarning = slot.status === 'APPROACHING_LIMIT'

  return (
    <div
      role="dialog"
      aria-modal="true"
      data-testid="drawer-inspection"
      className="drawer-panel inspection-card relative z-30 flex flex-col rounded-3xl border border-violet-400/30 bg-[#120526]/95 p-6 shadow-2xl backdrop-blur-2xl transition-all duration-300"
    >
      <div data-testid="slot-details" className="flex flex-col gap-4">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-violet-900/50 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-fuchsia-500/15 text-fuchsia-400">
              <Zap className="size-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold text-violet-300/70">DRAWER SLOT</span>
                <span className="rounded bg-violet-900/60 px-2 py-0.5 font-mono text-xs font-bold text-white">
                  {slot.slotNumber}
                </span>
              </div>
              <h3 className="font-mono text-lg font-bold text-white">{slot.partNumber}</h3>
            </div>
          </div>

          <button
            type="button"
            data-testid="close-drawer"
            onClick={onClose}
            aria-label="Close"
            className="flex size-8 items-center justify-center rounded-full border border-violet-700/50 bg-violet-950/50 text-violet-300 transition hover:bg-violet-800/60 hover:text-white"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Status Banner */}
        <div
          className={`flex items-center justify-between rounded-xl border p-3 font-mono text-xs ${
            isAlert
              ? 'border-rose-500/40 bg-rose-950/20 text-rose-300'
              : isWarning
              ? 'border-amber-500/40 bg-amber-950/20 text-amber-300'
              : 'border-emerald-500/40 bg-emerald-950/20 text-emerald-300'
          }`}
        >
          <div className="flex items-center gap-2 font-bold">
            {isAlert ? (
              <ShieldAlert className="size-4 text-rose-400" />
            ) : isWarning ? (
              <AlertTriangle className="size-4 text-amber-400" />
            ) : (
              <CheckCircle2 className="size-4 text-emerald-400" />
            )}
            <span>STATUS: {slot.status}</span>
          </div>
          <span className="text-[11px] text-purple-300/70">
            {slot.temperature} · {slot.humidity}
          </span>
        </div>

        {/* Detailed Parameters Grid - Matching exact Playwright required tokens */}
        <div className="grid grid-cols-2 gap-3 text-xs font-mono">
          <div className="rounded-xl border border-violet-900/40 bg-violet-950/30 p-3">
            <span className="text-[10px] text-purple-300/60">Part Number</span>
            <p className="mt-1 font-bold text-white">{slot.partNumber}</p>
          </div>

          <div className="rounded-xl border border-violet-900/40 bg-violet-950/30 p-3">
            <span className="text-[10px] text-purple-300/60">Batch ID</span>
            <p className="mt-1 font-bold text-white">{slot.batchId}</p>
          </div>

          <div className="rounded-xl border border-violet-900/40 bg-violet-950/30 p-3">
            <span className="text-[10px] text-purple-300/60">Shelf Life</span>
            <p className="mt-1 font-bold text-white">{slot.shelfLife}</p>
          </div>

          <div className="rounded-xl border border-violet-900/40 bg-violet-950/30 p-3">
            <span className="text-[10px] text-purple-300/60">Remaining</span>
            <p className="mt-1 font-bold text-emerald-300">{slot.remaining}</p>
          </div>
        </div>

        {/* Degradation Metric Box */}
        <div className="rounded-xl border border-violet-900/40 bg-gradient-to-r from-violet-950/40 to-fuchsia-950/30 p-3 font-mono text-xs">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-purple-300/60">Degradation</span>
            <span className="text-[10px] font-bold text-amber-300">Kinetic Model (0.60 eV)</span>
          </div>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-base font-bold text-white">{slot.degradation}</span>
            <span className="text-[10px] text-purple-300/60">Qty in Slot: {slot.quantity} units</span>
          </div>
        </div>

        {/* Actions Bar */}
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3 border-t border-violet-900/40 pt-4 font-mono text-xs">
          <button
            type="button"
            data-testid="dispatch-slot"
            onClick={() => onDispatch ? onDispatch(slot.id, 5) : null}
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-fuchsia-600 to-indigo-600 px-4 py-2.5 font-bold text-white shadow-lg shadow-fuchsia-600/30 transition hover:from-fuchsia-500 hover:to-indigo-500 active:scale-95"
          >
            <Zap className="size-3.5" />
            <span>Issue FEFO Pick (-5 units)</span>
          </button>

          <div className="flex items-center gap-2">
            <button
              type="button"
              data-testid="locate-slot"
              onClick={() => onLocate(slot.id)}
              className={`flex items-center gap-2 rounded-xl px-4 py-2.5 font-bold transition active:scale-95 ${
                slot.isLocated
                  ? 'bg-emerald-500 text-black shadow-[0_0_15px_rgba(16,185,129,0.7)] animate-pulse'
                  : 'border border-emerald-500/50 bg-emerald-950/40 text-emerald-300 hover:bg-emerald-900/50'
              }`}
            >
              <MapPin className="size-3.5" />
              <span>{slot.isLocated ? 'Beacon Active' : 'Locate LED'}</span>
            </button>

            <button
              type="button"
              data-testid="close-drawer"
              onClick={onClose}
              className="rounded-xl border border-violet-800/50 bg-violet-950/40 px-4 py-2.5 font-bold text-violet-200 transition hover:bg-violet-900/60 hover:text-white"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
