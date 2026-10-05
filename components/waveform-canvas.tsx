'use client'

import React, { useEffect, useRef, useState } from 'react'
import { Activity, Waves } from 'lucide-react'
import { useTelemetryWs } from '@/lib/use-telemetry-ws'

interface WaveformCanvasProps {
  cabinetLocation?: string
}

export function WaveformCanvas({ cabinetLocation = 'CAB-A' }: WaveformCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const { telemetry } = useTelemetryWs(cabinetLocation)

  // Keep a running buffer of history values for realistic oscilloscope plotting
  const historyRef = useRef<{ temp: number[]; hum: number[]; phase: number }>({
    temp: new Array(60).fill(24.5),
    hum: new Array(60).fill(45.2),
    phase: 0,
  })

  const [activeChannel, setActiveChannel] = useState<'both' | 'temp' | 'hum'>('both')

  // Push new telemetry points when updated
  useEffect(() => {
    const h = historyRef.current
    h.temp.push(telemetry.temperature_c)
    if (h.temp.length > 80) h.temp.shift()

    h.hum.push(telemetry.humidity_percent)
    if (h.hum.length > 80) h.hum.shift()
  }, [telemetry.temperature_c, telemetry.humidity_percent])

  useEffect(() => {
    let animationFrameId: number
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d', { alpha: true })
    if (!ctx) return

    // High DPI scaling with strict dimension preservation to avoid layout shift (CLS < 0.05)
    const resizeCanvas = () => {
      if (!canvas || !containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const dpr = window.devicePixelRatio || 1
      const width = Math.floor(rect.width)
      const height = Math.floor(rect.height)

      if (width > 0 && height > 0) {
        if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
          canvas.width = width * dpr
          canvas.height = height * dpr
          canvas.style.width = `${width}px`
          canvas.style.height = `${height}px`
          ctx.scale(dpr, dpr)
        }
      }
    }

    resizeCanvas()
    window.addEventListener('resize', resizeCanvas)

    let lastTime = performance.now()

    const render = (time: number) => {
      animationFrameId = requestAnimationFrame(render)

      // Time delta for smooth phase progression
      const delta = (time - lastTime) / 1000
      lastTime = time
      historyRef.current.phase += delta * 2.5

      const width = canvas.width / (window.devicePixelRatio || 1)
      const height = canvas.height / (window.devicePixelRatio || 1)
      if (width <= 0 || height <= 0) return

      // Clear with dark cyber phosphor trail
      ctx.clearRect(0, 0, width, height)

      // Cyber oscilloscope background grid
      ctx.strokeStyle = 'rgba(139, 92, 246, 0.08)'
      ctx.lineWidth = 1
      const gridSpacing = 28

      ctx.beginPath()
      for (let x = 0; x < width; x += gridSpacing) {
        ctx.moveTo(x, 0)
        ctx.lineTo(x, height)
      }
      for (let y = 0; y < height; y += gridSpacing) {
        ctx.moveTo(0, y)
        ctx.lineTo(width, y)
      }
      ctx.stroke()

      // Center reference line
      ctx.strokeStyle = 'rgba(192, 132, 252, 0.15)'
      ctx.setLineDash([4, 4])
      ctx.beginPath()
      ctx.moveTo(0, height / 2)
      ctx.lineTo(width, height / 2)
      ctx.stroke()
      ctx.setLineDash([])

      const phase = historyRef.current.phase
      const tempPoints = historyRef.current.temp
      const humPoints = historyRef.current.hum

      // 1. Draw Humidity Waveform (Cyan / Indigo channel)
      if (activeChannel === 'both' || activeChannel === 'hum') {
        ctx.save()
        ctx.strokeStyle = '#06b6d4'
        ctx.shadowColor = 'rgba(6, 182, 212, 0.6)'
        ctx.shadowBlur = 8
        ctx.lineWidth = 2
        ctx.beginPath()

        const stepX = width / Math.max(tempPoints.length - 1, 1)
        for (let i = 0; i < humPoints.length; i++) {
          const x = i * stepX
          const humVal = humPoints[i]
          // Map humidity (0 - 100%) to vertical range
          const normalized = (humVal - 30) / 40 // centered around 50%
          const sineMod = Math.sin(phase + i * 0.18) * 4
          const y = height / 2 + normalized * (height * 0.28) + sineMod

          if (i === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        }
        ctx.stroke()
        ctx.restore()
      }

      // 2. Draw Temperature Waveform (Neon Fuchsia / Violet channel)
      if (activeChannel === 'both' || activeChannel === 'temp') {
        ctx.save()
        ctx.strokeStyle = '#e879f9'
        ctx.shadowColor = 'rgba(232, 121, 249, 0.8)'
        ctx.shadowBlur = 10
        ctx.lineWidth = 2.5
        ctx.beginPath()

        const stepX = width / Math.max(tempPoints.length - 1, 1)
        for (let i = 0; i < tempPoints.length; i++) {
          const x = i * stepX
          const tempVal = tempPoints[i]
          // Map temp (15 - 35°C) to vertical range
          const normalized = (tempVal - 25) / 15
          const sineMod = Math.sin(phase * 1.2 + i * 0.25) * 6
          const y = height / 2 - normalized * (height * 0.3) + sineMod

          if (i === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        }
        ctx.stroke()

        // Draw active pulse cursor dot at the leading edge
        const lastX = width
        const latestTemp = tempPoints[tempPoints.length - 1]
        const latestNorm = (latestTemp - 25) / 15
        const lastY = height / 2 - latestNorm * (height * 0.3) + Math.sin(phase * 1.2 + tempPoints.length * 0.25) * 6

        ctx.fillStyle = '#ffffff'
        ctx.shadowColor = '#e879f9'
        ctx.shadowBlur = 12
        ctx.beginPath()
        ctx.arc(lastX - 4, lastY, 3.5, 0, Math.PI * 2)
        ctx.fill()
        ctx.restore()
      }
    }

    animationFrameId = requestAnimationFrame(render)

    return () => {
      cancelAnimationFrame(animationFrameId)
      window.removeEventListener('resize', resizeCanvas)
    }
  }, [activeChannel])

  return (
    <div className="relative flex flex-col rounded-3xl border border-slate-200/80 bg-white p-5 shadow-sm backdrop-blur-xl">
      {/* Waveform Header */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-lg bg-sky-50 text-sky-600 border border-sky-100">
            <Activity className="size-4 animate-pulse" />
          </div>
          <div>
            <span className="font-mono text-xs font-bold tracking-wider text-slate-900">
              ENVIRONMENTAL OSCILLOSCOPE
            </span>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono text-slate-400">60 FPS BUFFER</span>
              <span className="size-1 rounded-full bg-emerald-500" />
              <span className="text-[10px] font-mono text-emerald-600 font-semibold">REAL-TIME</span>
            </div>
          </div>
        </div>

        {/* Channel selector buttons */}
        <div className="flex items-center gap-1 rounded-xl border border-slate-200 bg-slate-50 p-1 text-[11px] font-mono">
          <button
            type="button"
            onClick={() => setActiveChannel('both')}
            className={`rounded-lg px-2.5 py-1 transition font-medium ${
              activeChannel === 'both' ? 'bg-sky-600 text-white shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            DUAL
          </button>
          <button
            type="button"
            onClick={() => setActiveChannel('temp')}
            className={`rounded-lg px-2.5 py-1 transition font-medium ${
              activeChannel === 'temp' ? 'bg-sky-600 text-white shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            TEMP
          </button>
          <button
            type="button"
            onClick={() => setActiveChannel('hum')}
            className={`rounded-lg px-2.5 py-1 transition font-medium ${
              activeChannel === 'hum' ? 'bg-sky-600 text-white shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            HUM
          </button>
        </div>
      </div>

      {/* Oscilloscope Canvas Viewport with STRICT FIXED DIMENSIONS & CLS < 0.05 GUARANTEE */}
      <div
        ref={containerRef}
        className="relative h-44 w-full overflow-hidden rounded-2xl border border-violet-900/40 bg-[#070114]/90 shadow-inner"
        style={{ minHeight: '176px', height: '176px' }}
      >
        <canvas
          ref={canvasRef}
          data-testid="waveform-canvas"
          className="sensor-canvas absolute inset-0 block h-full w-full"
        />

        {/* Oscilloscope telemetry HUD overlay readouts */}
        <div className="pointer-events-none absolute bottom-2 left-3 flex items-center gap-4 font-mono text-[11px]">
          <div className="flex items-center gap-1.5 text-fuchsia-300">
            <span className="size-2 rounded-full bg-fuchsia-400 shadow-[0_0_8px_#e879f9]" />
            <span>TEMP: {telemetry.temperature_c.toFixed(1)}°C</span>
          </div>
          <div className="flex items-center gap-1.5 text-cyan-300">
            <span className="size-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#06b6d4]" />
            <span>HUM: {telemetry.humidity_percent.toFixed(1)}%</span>
          </div>
        </div>

        <div className="pointer-events-none absolute right-3 top-2 font-mono text-[10px] text-purple-400/50">
          SMPL: 60Hz · EMA-SMOOTHED
        </div>
      </div>
    </div>
  )
}
