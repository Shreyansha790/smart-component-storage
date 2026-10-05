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
      className="drawer-panel inspection-card relative z-30 flex flex-col rounded-3xl border border-slate-200 bg-white p-6 shadow-xl backdrop-blur-2xl transition-all duration-300"
    >
      <div data-testid="slot-details" className="flex flex-col gap-4">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-200 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-sky-50 text-sky-600 border border-sky-100">
              <Zap className="size-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold text-slate-500">DRAWER SLOT</span>
                <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs font-bold text-slate-900 border border-slate-200">
                  {slot.slotNumber}
                </span>
              </div>
              <h3 className="font-mono text-lg font-bold text-slate-900">{slot.partNumber}</h3>
            </div>
          </div>

          <button
            type="button"
            data-testid="close-drawer"
            onClick={onClose}
            aria-label="Close"
            className="flex size-8 items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 shadow-sm"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Status Banner */}
        <div
          className={`flex items-center justify-between rounded-xl border p-3 font-mono text-xs ${
            isAlert
              ? 'border-rose-200 bg-rose-50 text-rose-700'
              : isWarning
              ? 'border-amber-200 bg-amber-50 text-amber-700'
              : 'border-emerald-200 bg-emerald-50 text-emerald-700'
          }`}
        >
          <div className="flex items-center gap-2 font-bold">
            {isAlert ? (
              <ShieldAlert className="size-4 text-rose-600" />
            ) : isWarning ? (
              <AlertTriangle className="size-4 text-amber-600" />
            ) : (
              <CheckCircle2 className="size-4 text-emerald-600" />
            )}
            <span>STATUS: {slot.status}</span>
          </div>
          <span className="text-[11px] text-slate-500">
            {slot.temperature} · {slot.humidity}
          </span>
        </div>

        {/* Detailed Parameters Grid - Matching exact Playwright required tokens */}
        <div className="grid grid-cols-2 gap-3 text-xs font-mono">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <span className="text-[10px] text-slate-500">Part Number</span>
            <p className="mt-1 font-bold text-slate-900">{slot.partNumber}</p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <span className="text-[10px] text-slate-500">Batch ID</span>
            <p className="mt-1 font-bold text-slate-900">{slot.batchId}</p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <span className="text-[10px] text-slate-500">Shelf Life</span>
            <p className="mt-1 font-bold text-slate-900">{slot.shelfLife}</p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <span className="text-[10px] text-slate-500">Remaining</span>
            <p className="mt-1 font-bold text-emerald-600">{slot.remaining}</p>
          </div>
        </div>

        {/* Degradation Metric Box */}
        <div className="rounded-xl border border-slate-200 bg-gradient-to-r from-slate-50 to-sky-50/50 p-3 font-mono text-xs">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-slate-500">Degradation</span>
            <span className="text-[10px] font-bold text-amber-600">Kinetic Model (0.60 eV)</span>
          </div>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-base font-bold text-slate-900">{slot.degradation}</span>
            <span className="text-[10px] text-slate-500">Qty in Slot: {slot.quantity} units</span>
          </div>
        </div>

        {/* Actions Bar */}
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-4 font-mono text-xs">
          <button
            type="button"
            data-testid="dispatch-slot"
            onClick={() => onDispatch ? onDispatch(slot.id, 5) : null}
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-600 to-indigo-600 px-4 py-2.5 font-bold text-white shadow-md shadow-sky-600/20 transition hover:from-sky-500 hover:to-indigo-500 active:scale-95"
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
                  ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/30 animate-pulse'
                  : 'border border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
              }`}
            >
              <MapPin className="size-3.5" />
              <span>{slot.isLocated ? 'Beacon Active' : 'Locate LED'}</span>
            </button>

            <button
              type="button"
              data-testid="close-drawer"
              onClick={onClose}
              className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 font-bold text-slate-700 transition hover:bg-slate-100 hover:text-slate-900 shadow-sm"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
