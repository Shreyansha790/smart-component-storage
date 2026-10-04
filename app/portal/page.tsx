'use client'

import React, { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import {
  Cpu,
  Layers,
  Activity,
  AlertTriangle,
  Flame,
  Droplets,
  PackageCheck,
  ChevronRight,
  Maximize2,
  RefreshCw,
  PlusCircle,
  Clock,
  Sparkles,
} from 'lucide-react'

interface SlotItem {
  id: string
  partNumber: string | null
  manufacturer: string | null
  category: string | null
  qty: number
  batch: string | null
  storedDays: number
  shelfLifeDays: number
  status: 'OK' | 'APPROACHING_LIMIT' | 'EXPIRED' | 'EMPTY'
  msl: string | null
  minTemp: number | null
  maxTemp: number | null
  maxHum: number | null
}

const INITIAL_SLOTS: SlotItem[] = [
  { id: 'A1', partNumber: 'ATmega328P-PU', manufacturer: 'Microchip', category: 'Microcontroller', qty: 250, batch: 'MC-2024-01', storedDays: 45, shelfLifeDays: 365, status: 'OK', msl: 'MSL-1', minTemp: 10, maxTemp: 35, maxHum: 60 },
  { id: 'A2', partNumber: 'STM32F401RET6', manufacturer: 'STMicroelectronics', category: 'Microcontroller', qty: 150, batch: 'ST-9942', storedDays: 354, shelfLifeDays: 365, status: 'APPROACHING_LIMIT', msl: 'MSL-3', minTemp: 15, maxTemp: 30, maxHum: 40 },
  { id: 'A3', partNumber: 'LM2596S-5.0', manufacturer: 'Texas Instruments', category: 'Power IC', qty: 400, batch: 'TI-8812', storedDays: 80, shelfLifeDays: 730, status: 'OK', msl: 'MSL-2', minTemp: 5, maxTemp: 40, maxHum: 65 },
  { id: 'A4', partNumber: 'BME280 Sensor', manufacturer: 'Bosch Sensortec', category: 'Sensor', qty: 85, batch: 'BS-4401', storedDays: 310, shelfLifeDays: 365, status: 'APPROACHING_LIMIT', msl: 'MSL-1', minTemp: 15, maxTemp: 28, maxHum: 50 },
  { id: 'B1', partNumber: 'ESP32-WROOM-32E', manufacturer: 'Espressif', category: 'Microcontroller', qty: 300, batch: 'ES-3312', storedDays: 20, shelfLifeDays: 365, status: 'OK', msl: 'MSL-3', minTemp: 10, maxTemp: 30, maxHum: 45 },
  { id: 'B2', partNumber: null, manufacturer: null, category: null, qty: 0, batch: null, storedDays: 0, shelfLifeDays: 0, status: 'EMPTY', msl: null, minTemp: null, maxTemp: null, maxHum: null },
  { id: 'B3', partNumber: 'Nichicon 1000uF', manufacturer: 'Nichicon', category: 'Capacitor', qty: 120, batch: 'NC-1092', storedDays: 390, shelfLifeDays: 365, status: 'EXPIRED', msl: 'Standard', minTemp: 15, maxTemp: 35, maxHum: 55 },
  { id: 'B4', partNumber: 'MPU-6050 IMU', manufacturer: 'TDK InvenSense', category: 'Sensor', qty: 65, batch: 'IV-5510', storedDays: 140, shelfLifeDays: 365, status: 'OK', msl: 'MSL-2', minTemp: 10, maxTemp: 30, maxHum: 40 },
  { id: 'C1', partNumber: 'W25Q128JV Flash', manufacturer: 'Winbond', category: 'Memory', qty: 50, batch: 'WB-0041', storedDays: 110, shelfLifeDays: 730, status: 'OK', msl: 'MSL-3', minTemp: 10, maxTemp: 35, maxHum: 40 },
  { id: 'C2', partNumber: null, manufacturer: null, category: null, qty: 0, batch: null, storedDays: 0, shelfLifeDays: 0, status: 'EMPTY', msl: null, minTemp: null, maxTemp: null, maxHum: null },
  { id: 'C3', partNumber: null, manufacturer: null, category: null, qty: 0, batch: null, storedDays: 0, shelfLifeDays: 0, status: 'EMPTY', msl: null, minTemp: null, maxTemp: null, maxHum: null },
  { id: 'C4', partNumber: 'PCA9685 PWM Driver', manufacturer: 'NXP Semi', category: 'Power IC', qty: 210, batch: 'NX-8821', storedDays: 60, shelfLifeDays: 365, status: 'OK', msl: 'MSL-1', minTemp: 10, maxTemp: 40, maxHum: 50 },
]

export default function MotionPortalPage() {
  const [slots, setSlots] = useState<SlotItem[]>(INITIAL_SLOTS)
  const [selectedSlotId, setSelectedSlotId] = useState<string>('A2')
  const [isIsometric, setIsIsometric] = useState<boolean>(true)
  const [liveTemp, setLiveTemp] = useState<number>(21.8)
  const [liveHumidity, setLiveHumidity] = useState<number>(36.4)
  const [isAlertActive, setIsAlertActive] = useState<boolean>(false)
  const [telemetryHistory, setTelemetryHistory] = useState<number[]>([21.8, 22.0, 21.7, 21.9, 22.1, 21.8, 21.6, 21.9])
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  const selectedSlot = slots.find((s) => s.id === selectedSlotId) || slots[0]

  // Periodic Telemetry Simulation
  useEffect(() => {
    const timer = setInterval(() => {
      setLiveTemp((prev) => {
        const delta = (Math.random() - 0.5) * 0.25
        const updated = Number(Math.max(16, Math.min(38, prev + delta)).toFixed(1))
        setTelemetryHistory((hist) => [...hist.slice(1), updated])
        return updated
      })
      setLiveHumidity((prev) => {
        const delta = (Math.random() - 0.5) * 0.4
        return Number(Math.max(20, Math.min(75, prev + delta)).toFixed(1))
      })
    }, 1500)
    return () => clearInterval(timer)
  }, [])

  // Canvas Waveform rendering
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    canvas.width = canvas.parentElement?.clientWidth || 400
    canvas.height = canvas.parentElement?.clientHeight || 120

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Grid Lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)'
    ctx.lineWidth = 1
    for (let y = 15; y < canvas.height; y += 25) {
      ctx.beginPath()
      ctx.moveTo(0, y)
      ctx.lineTo(canvas.width, y)
      ctx.stroke()
    }

    // Gradient wave line
    const step = canvas.width / (telemetryHistory.length - 1)
    ctx.beginPath()
    ctx.strokeStyle = '#d946ef'
    ctx.lineWidth = 3
    telemetryHistory.forEach((val, i) => {
      const y = canvas.height - ((val - 15) / 25) * canvas.height
      if (i === 0) ctx.moveTo(0, y)
      else ctx.lineTo(i * step, y)
    })
    ctx.stroke()
  }, [telemetryHistory])

  const triggerSpike = (type: 'heat' | 'humidity') => {
    setIsAlertActive(true)
    if (type === 'heat') {
      setLiveTemp((t) => Number((t + 9.5).toFixed(1)))
    } else {
      setLiveHumidity((h) => Number((h + 26).toFixed(1)))
    }
    setTimeout(() => {
      setIsAlertActive(false)
      setLiveTemp(21.8)
      setLiveHumidity(36.4)
    }, 5000)
  }

  const dispatchBatch = () => {
    if (!selectedSlot || selectedSlot.qty <= 0) return
    setSlots((prev) =>
      prev.map((s) => (s.id === selectedSlot.id ? { ...s, qty: Math.max(0, s.qty - 10) } : s))
    )
  }

  const fefoQueue = [...slots]
    .filter((s) => s.status !== 'EMPTY' && s.qty > 0)
    .sort((a, b) => (a.shelfLifeDays - a.storedDays) - (b.shelfLifeDays - b.storedDays))

  return (
    <div className="min-h-screen w-full bg-[#07030d] text-white p-4 md:p-8 font-sans selection:bg-fuchsia-500 selection:text-white">
      {/* Background radial lights */}
      <div className="fixed top-0 left-1/4 -z-10 h-[500px] w-[500px] rounded-full bg-fuchsia-600/10 blur-[140px] pointer-events-none" />
      <div className="fixed bottom-0 right-1/4 -z-10 h-[500px] w-[500px] rounded-full bg-violet-600/10 blur-[150px] pointer-events-none" />

      {/* Top Navbar */}
      <header className="mx-auto max-w-7xl mb-8 flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-violet-500/20 bg-zinc-950/70 p-5 backdrop-blur-2xl shadow-2xl">
        <div className="flex items-center gap-4">
          <div className="relative flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-fuchsia-600 to-indigo-600 text-white shadow-lg shadow-fuchsia-600/30">
            <Cpu className="h-6 w-6" />
            <span className="absolute -top-1 -right-1 flex h-3 w-3">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-500" />
            </span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl md:text-2xl font-extrabold tracking-tight text-white">
                AeroStore<span className="text-fuchsia-400"> 3D</span>
              </h1>
              <span className="rounded-full border border-fuchsia-500/30 bg-fuchsia-500/10 px-2 py-0.5 text-xs font-mono text-fuchsia-300">
                PRO ACTIVE
              </span>
            </div>
            <p className="text-xs text-zinc-400">Smart Electronic Component Storage • Automated FEFO & IoT Telemetry</p>
          </div>
        </div>

        <div className="flex items-center gap-3 font-mono text-xs">
          <div className={`flex items-center gap-2 rounded-xl border px-3 py-2 ${isAlertActive ? 'border-rose-500/50 bg-rose-950/40 text-rose-300' : 'border-zinc-800 bg-zinc-900/60 text-emerald-400'}`}>
            <span className={`h-2 w-2 rounded-full ${isAlertActive ? 'bg-rose-400 animate-ping' : 'bg-emerald-400 animate-pulse'}`} />
            <span>ESP32: {isAlertActive ? 'BREACH SPIKE' : 'SYNCED (38ms)'}</span>
          </div>

          <button
            onClick={() => setIsIsometric(!isIsometric)}
            className="flex items-center gap-1.5 rounded-xl bg-fuchsia-600 px-4 py-2 font-semibold text-white shadow-lg shadow-fuchsia-600/30 transition hover:bg-fuchsia-500 hover:scale-105"
          >
            <Maximize2 className="h-3.5 w-3.5" />
            {isIsometric ? 'Front View' : '3D Isometric'}
          </button>

          <Link
            href="/dashboard"
            className="rounded-xl border border-zinc-700 bg-zinc-800/80 px-3.5 py-2 text-zinc-300 transition hover:bg-zinc-700"
          >
            Classic View
          </Link>
        </div>
      </header>

      {/* Metric Cards Banner */}
      <div className="mx-auto max-w-7xl mb-8 grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-violet-900/30 bg-zinc-950/60 p-4 backdrop-blur-xl">
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span className="font-semibold uppercase tracking-wider">Internal Temp</span>
            <Flame className="h-4 w-4 text-fuchsia-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold font-mono text-white">{liveTemp}</span>
            <span className="text-sm font-semibold text-zinc-400">°C</span>
          </div>
          <p className="mt-1 text-[11px] text-emerald-400">Target: 22.0°C (±1.5°C)</p>
        </div>

        <div className="rounded-2xl border border-violet-900/30 bg-zinc-950/60 p-4 backdrop-blur-xl">
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span className="font-semibold uppercase tracking-wider">Cabinet Humidity</span>
            <Droplets className="h-4 w-4 text-sky-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold font-mono text-white">{liveHumidity}</span>
            <span className="text-sm font-semibold text-zinc-400">% RH</span>
          </div>
          <p className="mt-1 text-[11px] text-sky-400">NEMA Dry-Shield Active</p>
        </div>

        <div className="rounded-2xl border border-violet-900/30 bg-zinc-950/60 p-4 backdrop-blur-xl">
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span className="font-semibold uppercase tracking-wider">FEFO Prioritized</span>
            <Clock className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold font-mono text-amber-300">2</span>
            <span className="text-sm font-semibold text-zinc-400">Batches &lt;14d</span>
          </div>
          <p className="mt-1 text-[11px] text-amber-300">STM32F401 (Slot A2)</p>
        </div>

        <div className="rounded-2xl border border-violet-900/30 bg-zinc-950/60 p-4 backdrop-blur-xl">
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span className="font-semibold uppercase tracking-wider">Active Inventory</span>
            <PackageCheck className="h-4 w-4 text-purple-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold font-mono text-white">1,630</span>
            <span className="text-sm font-semibold text-zinc-400">units</span>
          </div>
          <p className="mt-1 text-[11px] text-zinc-400">9 of 12 Drawers Occupied</p>
        </div>
      </div>

      {/* Main Grid: 3D Cabinet on Left, Details & Queue on Right */}
      <div className="mx-auto max-w-7xl grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left Column: 3D Cabinet & Oscilloscope */}
        <div className="lg:col-span-7 flex flex-col gap-6">
          <div className="rounded-3xl border border-violet-500/20 bg-zinc-950/70 p-6 backdrop-blur-2xl shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <span>Physical Cabinet Array [Rack A-01]</span>
                  <span className="rounded bg-indigo-500/20 px-2 py-0.5 text-[11px] font-mono text-indigo-300 border border-indigo-500/30">
                    ISOLATED
                  </span>
                </h2>
                <p className="text-xs text-zinc-400">Select any physical drawer to review components and issue dispatches.</p>
              </div>
              <div className="flex items-center gap-3 text-xs text-zinc-400">
                <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-emerald-500" /> Safe</span>
                <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-amber-500" /> Warn</span>
                <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-rose-500" /> Alert</span>
              </div>
            </div>

            {/* 3D Cabinet Rack Viewport */}
            <div
              className="py-10 px-6 rounded-2xl border border-violet-900/40 bg-zinc-900/40 overflow-hidden relative"
              style={{ perspective: '1100px' }}
            >
              <div
                className="grid grid-cols-4 gap-4 transition-transform duration-700 ease-out"
                style={{
                  transformStyle: 'preserve-3d',
                  transform: isIsometric
                    ? 'rotateX(22deg) rotateY(-16deg) rotateZ(4deg)'
                    : 'rotateX(0deg) rotateY(0deg) rotateZ(0deg)',
                }}
              >
                {slots.map((slot) => {
                  const isSelected = slot.id === selectedSlotId
                  const remaining = Math.max(0, slot.shelfLifeDays - slot.storedDays)

                  let borderClass = 'border-zinc-800 bg-zinc-900/50'
                  let badgeClass = 'bg-zinc-800 text-zinc-400'

                  if (slot.status === 'OK') {
                    borderClass = 'border-emerald-800/40 bg-emerald-950/20 hover:border-emerald-500'
                    badgeClass = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                  } else if (slot.status === 'APPROACHING_LIMIT') {
                    borderClass = 'border-amber-700/50 bg-amber-950/30 hover:border-amber-400'
                    badgeClass = 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                  } else if (slot.status === 'EXPIRED') {
                    borderClass = 'border-rose-700/50 bg-rose-950/30 hover:border-rose-400'
                    badgeClass = 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                  }

                  return (
                    <div
                      key={slot.id}
                      onClick={() => setSelectedSlotId(slot.id)}
                      className={`group relative flex h-28 flex-col justify-between rounded-xl border p-3 cursor-pointer transition-all duration-300 ${borderClass} ${
                        isSelected
                          ? 'ring-2 ring-fuchsia-500 shadow-[0_0_30px_rgba(217,70,239,0.35)] -translate-y-2'
                          : 'hover:-translate-y-1'
                      }`}
                      style={{
                        transformStyle: 'preserve-3d',
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-bold text-zinc-400">{slot.id}</span>
                        <span className={`rounded px-1.5 py-0.5 text-[10px] font-mono border ${badgeClass}`}>
                          {slot.status === 'EMPTY' ? 'EMPTY' : slot.status === 'APPROACHING_LIMIT' ? 'WARN' : slot.status}
                        </span>
                      </div>

                      <div className="my-auto">
                        {slot.partNumber ? (
                          <>
                            <p className="truncate text-xs font-semibold text-white">{slot.partNumber}</p>
                            <p className="truncate text-[11px] text-zinc-400 font-mono">{slot.qty} units</p>
                          </>
                        ) : (
                          <p className="text-[11px] text-zinc-600 text-center">Unoccupied</p>
                        )}
                      </div>

                      <div className="flex items-center justify-between border-t border-zinc-800/80 pt-1 text-[10px] text-zinc-500 font-mono">
                        <span>{slot.msl || '--'}</span>
                        <span>{slot.shelfLifeDays ? `${remaining}d` : '--'}</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Hardware Telemetry Stress Simulators */}
            <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4">
              <span className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5">
                <Sparkles className="h-4 w-4 text-fuchsia-400" />
                Live Sensor Telemetry Diagnostics:
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => triggerSpike('heat')}
                  className="rounded-xl border border-rose-800/50 bg-rose-950/40 px-3 py-1.5 text-xs font-semibold text-rose-300 transition hover:bg-rose-900"
                >
                  Trigger Heat Spike (+9.5°C)
                </button>
                <button
                  onClick={() => triggerSpike('humidity')}
                  className="rounded-xl border border-sky-800/50 bg-sky-950/40 px-3 py-1.5 text-xs font-semibold text-sky-300 transition hover:bg-sky-900"
                >
                  Trigger Humidity Breach (+26%)
                </button>
              </div>
            </div>
          </div>

          {/* Oscilloscope Waveform Panel */}
          <div className="rounded-3xl border border-violet-500/20 bg-zinc-950/70 p-6 backdrop-blur-2xl">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                  <Activity className="h-4 w-4 text-fuchsia-400" />
                  Real-Time Sensor Bus Oscilloscope
                </h3>
                <p className="text-xs text-zinc-400">Streamed via ESP32 I2C sensor bus every 1500ms</p>
              </div>
              <span className="font-mono text-xs text-fuchsia-400">TEMP & HUMIDITY STREAM</span>
            </div>
            <div className="h-32 w-full rounded-2xl border border-zinc-800 bg-zinc-950/90 p-2 overflow-hidden">
              <canvas ref={canvasRef} className="h-full w-full block" />
            </div>
          </div>
        </div>

        {/* Right Column: Slot Detail & FEFO Dispatch Queue */}
        <div className="lg:col-span-5 flex flex-col gap-6">
          {/* Selected Drawer Inspector */}
          <div className="rounded-3xl border border-violet-500/20 bg-zinc-950/70 p-6 backdrop-blur-2xl shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-zinc-800">
              <div>
                <span className="font-mono text-xs font-bold uppercase tracking-widest text-fuchsia-400">
                  SLOT {selectedSlot.id} INSPECTOR
                </span>
                <h3 className="text-xl font-black text-white mt-0.5">
                  {selectedSlot.partNumber || 'Empty Drawer'}
                </h3>
                <p className="text-xs text-zinc-400">
                  {selectedSlot.manufacturer ? `${selectedSlot.manufacturer} • ${selectedSlot.category}` : 'Slot available for allocation'}
                </p>
              </div>
              <span className={`rounded-full px-3 py-1 text-xs font-mono font-bold border ${
                selectedSlot.status === 'OK'
                  ? 'border-emerald-500/40 bg-emerald-500/20 text-emerald-300'
                  : selectedSlot.status === 'APPROACHING_LIMIT'
                  ? 'border-amber-500/40 bg-amber-500/20 text-amber-300'
                  : selectedSlot.status === 'EXPIRED'
                  ? 'border-rose-500/40 bg-rose-500/20 text-rose-300'
                  : 'border-zinc-700 bg-zinc-800 text-zinc-400'
              }`}>
                {selectedSlot.status}
              </span>
            </div>

            <div className="my-5 grid grid-cols-2 gap-3">
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-3">
                <span className="text-[11px] font-semibold text-zinc-400 uppercase">Stock On Hand</span>
                <p className="mt-1 font-mono text-xl font-bold text-white">{selectedSlot.qty} units</p>
                <span className="font-mono text-[11px] text-zinc-500">Batch: #{selectedSlot.batch || 'None'}</span>
              </div>

              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-3">
                <span className="text-[11px] font-semibold text-zinc-400 uppercase">Moisture Class</span>
                <p className="mt-1 font-mono text-xl font-bold text-fuchsia-300">{selectedSlot.msl || 'N/A'}</p>
                <span className="text-[11px] text-zinc-500">Floor Life: 168h</span>
              </div>

              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-3">
                <span className="text-[11px] font-semibold text-zinc-400 uppercase">Safe Limits</span>
                <p className="mt-1 font-mono text-sm font-semibold text-zinc-200">
                  {selectedSlot.minTemp ?? 15}°C ~ {selectedSlot.maxTemp ?? 35}°C
                </p>
                <span className="text-[11px] text-emerald-400">&lt; {selectedSlot.maxHum ?? 45}% RH</span>
              </div>

              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-3">
                <span className="text-[11px] font-semibold text-zinc-400 uppercase">Shelf Life</span>
                <p className="mt-1 font-mono text-sm font-semibold text-amber-300">
                  {selectedSlot.shelfLifeDays ? `${Math.max(0, selectedSlot.shelfLifeDays - selectedSlot.storedDays)}d remaining` : 'N/A'}
                </p>
                <span className="text-[11px] text-zinc-500">{selectedSlot.storedDays}d in storage</span>
              </div>
            </div>

            {/* Progress Bar */}
            {selectedSlot.shelfLifeDays > 0 && (
              <div className="mb-6">
                <div className="flex justify-between text-xs font-mono text-zinc-400 mb-1.5">
                  <span>Shelf Life Elapsed</span>
                  <span className="text-amber-300 font-bold">
                    {Math.min(100, Math.round((selectedSlot.storedDays / selectedSlot.shelfLifeDays) * 100))}%
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-zinc-800 overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-emerald-500 via-amber-500 to-rose-500 rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.min(100, Math.round((selectedSlot.storedDays / selectedSlot.shelfLifeDays) * 100))}%`,
                    }}
                  />
                </div>
              </div>
            )}

            <button
              onClick={dispatchBatch}
              disabled={selectedSlot.qty <= 0}
              className="w-full flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-fuchsia-600 to-indigo-600 py-3.5 text-sm font-bold text-white shadow-lg shadow-fuchsia-600/30 transition hover:from-fuchsia-500 hover:to-indigo-500 disabled:opacity-40"
            >
              <PackageCheck className="h-4 w-4" />
              <span>Issue FEFO Dispatch (-10 units)</span>
            </button>
          </div>

          {/* FEFO Queue Card */}
          <div className="rounded-3xl border border-violet-500/20 bg-zinc-950/70 p-6 backdrop-blur-2xl">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                  <Layers className="h-4 w-4 text-amber-400" />
                  FEFO Priority Pick Queue
                </h3>
                <p className="text-xs text-zinc-400">First-Expired, First-Out pick-and-place priority</p>
              </div>
              <span className="rounded bg-zinc-800 px-2 py-0.5 font-mono text-[11px] text-zinc-400">AUTOMATIC</span>
            </div>

            <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
              {fefoQueue.map((item, index) => {
                const remaining = Math.max(0, item.shelfLifeDays - item.storedDays)
                const isSelected = item.id === selectedSlotId

                return (
                  <div
                    key={item.id}
                    onClick={() => setSelectedSlotId(item.id)}
                    className={`flex items-center justify-between rounded-xl border p-3 transition cursor-pointer ${
                      isSelected
                        ? 'border-fuchsia-500/60 bg-fuchsia-950/40'
                        : 'border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800/80'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className={`flex h-6 w-6 items-center justify-center rounded-lg font-mono text-xs ${
                        index === 0 ? 'bg-rose-500/20 text-rose-300 font-bold' : 'bg-zinc-800 text-zinc-400'
                      }`}>
                        #{index + 1}
                      </span>
                      <div>
                        <p className="text-xs font-bold text-white">{item.partNumber}</p>
                        <p className="font-mono text-[11px] text-zinc-400">
                          Slot {item.id} • {item.qty} pcs
                        </p>
                      </div>
                    </div>

                    <div className="text-right">
                      <span className={`font-mono text-xs font-bold ${
                        remaining < 30 ? 'text-rose-400' : remaining < 60 ? 'text-amber-300' : 'text-emerald-400'
                      }`}>
                        {remaining}d left
                      </span>
                      <p className="text-[10px] text-zinc-500">Pick Next</p>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}
