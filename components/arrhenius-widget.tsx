'use client'

import React, { useState } from 'react'
import { Flame, Clock, Zap, ArrowRight, CheckCircle, AlertTriangle } from 'lucide-react'

export interface FefoItem {
  id: string
  name: string
  batch: string
  nominalDays: number
  stressHours: number
  accelFactor: number
  degradationScore: number
  effectiveDaysRemaining: number
  status: 'OPTIMAL' | 'APPROACHING_LIMIT' | 'EXPIRED'
}

const DEFAULT_FEFO_ITEMS: FefoItem[] = [
  {
    id: 'BAT-2026-X8',
    name: 'ESP32-WROOM-32D',
    batch: 'BAT-2026-X8',
    nominalDays: 365,
    stressHours: 14.5,
    accelFactor: 1.48,
    degradationScore: 0.28,
    effectiveDaysRemaining: 184,
    status: 'APPROACHING_LIMIT',
  },
  {
    id: 'BAT-2026-C2',
    name: 'SHT31-DIS-B Humidity Sensor',
    batch: 'BAT-2026-C2',
    nominalDays: 730,
    stressHours: 4.2,
    accelFactor: 1.08,
    degradationScore: 0.12,
    effectiveDaysRemaining: 610,
    status: 'OPTIMAL',
  },
  {
    id: 'BAT-2025-L9',
    name: 'STM32F401RE MCU',
    batch: 'BAT-2025-L9',
    nominalDays: 180,
    stressHours: 28.0,
    accelFactor: 2.15,
    degradationScore: 0.92,
    effectiveDaysRemaining: 12,
    status: 'EXPIRED',
  },
]

export function ArrheniusWidget() {
  const [selectedItem, setSelectedItem] = useState<FefoItem>(DEFAULT_FEFO_ITEMS[0])

  return (
    <div className="relative flex flex-col rounded-3xl border border-slate-200/80 bg-white p-5 shadow-sm backdrop-blur-xl">
      {/* Widget Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-lg bg-amber-50 text-amber-600 border border-amber-100">
            <Flame className="size-4" />
          </div>
          <div>
            <span className="font-mono text-xs font-bold tracking-wider text-slate-900">
              ARRHENIUS DYNAMIC FEFO ENGINE
            </span>
            <p className="text-[10px] font-mono text-slate-400">
              PHYSICS-INFORMED KINETIC DEGRADATION (Ea = 0.6 eV)
            </p>
          </div>
        </div>

        <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-amber-700">
          AF = {selectedItem.accelFactor.toFixed(2)}x
        </span>
      </div>

      {/* Degradation Metrics Banner */}
      <div className="grid grid-cols-3 gap-2.5 rounded-2xl border border-slate-200 bg-slate-50/80 p-3.5">
        <div className="flex flex-col">
          <span className="text-[10px] font-mono text-slate-500">Acceleration Factor</span>
          <span className="mt-1 font-mono text-xl font-bold text-amber-600">
            {selectedItem.accelFactor.toFixed(2)}×
          </span>
          <span className="text-[9px] font-mono text-slate-400">Arrhenius Rate</span>
        </div>

        <div className="flex flex-col border-x border-slate-200 px-3">
          <span className="text-[10px] font-mono text-slate-500">Cumulative Stress</span>
          <span className="mt-1 font-mono text-xl font-bold text-indigo-600">
            {selectedItem.stressHours.toFixed(1)} hrs
          </span>
          <span className="text-[9px] font-mono text-slate-400">Thermal Excursion</span>
        </div>

        <div className="flex flex-col pl-1">
          <span className="text-[10px] font-mono text-slate-500">Adjusted Remaining</span>
          <span className="mt-1 font-mono text-xl font-bold text-emerald-600">
            {selectedItem.effectiveDaysRemaining} d
          </span>
          <span className="text-[9px] font-mono text-slate-400">
            Nominal: {selectedItem.nominalDays}d
          </span>
        </div>
      </div>

      {/* Dynamic FEFO Queue List */}
      <div className="mt-4 flex flex-col gap-2">
        <div className="flex items-center justify-between text-[11px] font-mono text-slate-500">
          <span>PRIORITIZED FEFO DISPATCH QUEUE</span>
          <span className="text-[10px] text-slate-400">STRESS-WEIGHTED</span>
        </div>

        <div className="flex flex-col gap-2">
          {DEFAULT_FEFO_ITEMS.map((item) => {
            const isSelected = selectedItem.id === item.id
            const isAlert = item.status === 'EXPIRED'
            const isWarning = item.status === 'APPROACHING_LIMIT'

            return (
              <div
                key={item.id}
                onClick={() => setSelectedItem(item)}
                className={`flex cursor-pointer items-center justify-between rounded-xl border p-2.5 transition ${
                  isSelected
                    ? 'border-sky-300 bg-sky-50/80 ring-1 ring-sky-300 shadow-sm'
                    : 'border-slate-200 bg-slate-50/60 hover:bg-slate-100/70'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <div
                    className={`size-2 rounded-full ${
                      isAlert
                        ? 'bg-rose-500 shadow-sm'
                        : isWarning
                        ? 'bg-amber-500 shadow-sm'
                        : 'bg-emerald-500 shadow-sm'
                    }`}
                  />
                  <div>
                    <p className="font-mono text-xs font-bold text-slate-900">{item.name}</p>
                    <p className="text-[10px] font-mono text-slate-500">
                      Batch: {item.batch} · Degradation: {(item.degradationScore * 100).toFixed(0)}%
                    </p>
                  </div>
                </div>

                <div className="text-right font-mono">
                  <span
                    className={`text-xs font-bold ${
                      isAlert
                        ? 'text-rose-600'
                        : isWarning
                        ? 'text-amber-600'
                        : 'text-emerald-600'
                    }`}
                  >
                    {item.effectiveDaysRemaining} days
                  </span>
                  <p className="text-[9px] text-slate-400 font-medium">{item.status}</p>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
