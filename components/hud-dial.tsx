'use client'

import React from 'react'
import { Thermometer, Droplets, ShieldCheck, AlertTriangle } from 'lucide-react'
import { useTelemetryWs } from '@/lib/use-telemetry-ws'

interface HudDialProps {
  cabinetLocation?: string
}

export function HudDial({ cabinetLocation = 'CAB-A' }: HudDialProps) {
  const { telemetry } = useTelemetryWs(cabinetLocation)

  const temp = telemetry.temperature_c ?? 24.5
  const humidity = telemetry.humidity_percent ?? 45.2

  // Gauge calculations for SVG circular arcs
  // Map temp range: 0°C to 50°C -> 0 to 100%
  const tempPercent = Math.min(Math.max(((temp - 10) / 30) * 100, 0), 100)
  // Map humidity range: 0% to 100%
  const humPercent = Math.min(Math.max(humidity, 0), 100)

  const radius = 52
  const circumference = 2 * Math.PI * radius
  const tempOffset = circumference - (tempPercent / 100) * circumference * 0.75
  const humOffset = circumference - (humPercent / 100) * circumference * 0.75

  const isTempHigh = temp > 30
  const isHumHigh = humidity > 60

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {/* 1. Thermal Dial */}
      <div
        data-testid="temp-reading"
        className="temperature-dial relative flex items-center justify-between overflow-hidden rounded-3xl border border-slate-200/80 bg-white p-5 shadow-sm backdrop-blur-xl"
      >
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span className="flex size-7 items-center justify-center rounded-lg bg-sky-50 text-sky-600 border border-sky-100">
              <Thermometer className="size-4" />
            </span>
            <span className="font-mono text-xs font-semibold uppercase tracking-wider text-slate-500">
              Internal Temp
            </span>
          </div>

          <div className="mt-3 flex items-baseline gap-1">
            <span
              data-testid="telemetry-temp"
              className="temp-val font-mono text-3xl font-extrabold tracking-tight text-slate-900"
            >
              {temp.toFixed(1)}
            </span>
            <span className="font-mono text-sm font-semibold text-slate-500">°C</span>
          </div>

          <div className="mt-2 flex items-center gap-1.5 font-mono text-[11px]">
            {isTempHigh ? (
              <span className="flex items-center gap-1 text-amber-600">
                <AlertTriangle className="size-3" /> Excursion Alert
              </span>
            ) : (
              <span className="flex items-center gap-1 text-emerald-400">
                <ShieldCheck className="size-3" /> Nominal Range
              </span>
            )}
            <span className="text-purple-400/50">· Set: 22°C</span>
          </div>
        </div>

        {/* Circular SVG Gauge */}
        <div className="relative flex size-28 items-center justify-center">
          <svg className="size-full -rotate-135" viewBox="0 0 120 120">
            {/* Background track */}
            <circle
              cx="60"
              cy="60"
              r={radius}
              fill="none"
              stroke="rgba(139, 92, 246, 0.15)"
              strokeWidth="9"
              strokeDasharray={`${circumference * 0.75} ${circumference}`}
              strokeLinecap="round"
            />
            {/* Value progress arc */}
            <circle
              cx="60"
              cy="60"
              r={radius}
              fill="none"
              stroke={isTempHigh ? '#f59e0b' : '#c084fc'}
              strokeWidth="9"
              strokeDasharray={`${circumference * 0.75} ${circumference}`}
              strokeDashoffset={tempOffset}
              strokeLinecap="round"
              className="transition-all duration-700 ease-out"
              style={{
                filter: isTempHigh
                  ? 'drop-shadow(0 0 6px rgba(245, 158, 11, 0.7))'
                  : 'drop-shadow(0 0 6px rgba(192, 132, 252, 0.7))',
              }}
            />
          </svg>
          <div className="pointer-events-none absolute flex flex-col items-center justify-center text-center">
            <span className="font-mono text-[11px] font-bold text-violet-200">
              {tempPercent.toFixed(0)}%
            </span>
            <span className="text-[9px] font-mono text-purple-400/60">LOAD</span>
          </div>
        </div>
      </div>

      {/* 2. Relative Humidity Dial */}
      <div className="relative flex items-center justify-between overflow-hidden rounded-3xl border border-slate-200/80 bg-white p-5 shadow-sm backdrop-blur-xl">
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span className="flex size-7 items-center justify-center rounded-lg bg-sky-50 text-sky-600 border border-sky-100">
              <Droplets className="size-4" />
            </span>
            <span className="font-mono text-xs font-semibold uppercase tracking-wider text-slate-500">
              Humidity (RH)
            </span>
          </div>

          <div className="mt-3 flex items-baseline gap-1">
            <span className="font-mono text-3xl font-extrabold tracking-tight text-slate-900">
              {humidity.toFixed(1)}
            </span>
            <span className="font-mono text-sm font-semibold text-slate-500">%RH</span>
          </div>

          <div className="mt-2 flex items-center gap-1.5 font-mono text-[11px]">
            {isHumHigh ? (
              <span className="flex items-center gap-1 text-amber-600">
                <AlertTriangle className="size-3" /> High Moisture
              </span>
            ) : (
              <span className="flex items-center gap-1 text-emerald-600">
                <ShieldCheck className="size-3" /> Dry Chamber
              </span>
            )}
            <span className="text-slate-400">· Desiccant OK</span>
          </div>
        </div>

        {/* Circular SVG Gauge */}
        <div className="relative flex size-28 items-center justify-center">
          <svg className="size-full -rotate-135" viewBox="0 0 120 120">
            {/* Background track */}
            <circle
              cx="60"
              cy="60"
              r={radius}
              fill="none"
              stroke="rgba(6, 182, 212, 0.15)"
              strokeWidth="9"
              strokeDasharray={`${circumference * 0.75} ${circumference}`}
              strokeLinecap="round"
            />
            {/* Value progress arc */}
            <circle
              cx="60"
              cy="60"
              r={radius}
              fill="none"
              stroke={isHumHigh ? '#f59e0b' : '#06b6d4'}
              strokeWidth="9"
              strokeDasharray={`${circumference * 0.75} ${circumference}`}
              strokeDashoffset={humOffset}
              strokeLinecap="round"
              className="transition-all duration-700 ease-out"
              style={{
                filter: isHumHigh
                  ? 'drop-shadow(0 0 6px rgba(245, 158, 11, 0.7))'
                  : 'drop-shadow(0 0 6px rgba(6, 182, 212, 0.7))',
              }}
            />
          </svg>
          <div className="pointer-events-none absolute flex flex-col items-center justify-center text-center">
            <span className="font-mono text-[11px] font-bold text-cyan-200">
              {humPercent.toFixed(0)}%
            </span>
            <span className="text-[9px] font-mono text-cyan-400/60">RH</span>
          </div>
        </div>
      </div>
    </div>
  )
}
