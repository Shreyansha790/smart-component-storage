'use client'

import React, { useState } from 'react'
import { Fan, Snowflake, Cpu, Power, Compass } from 'lucide-react'
import { useTelemetryWs } from '@/lib/use-telemetry-ws'

interface ActuatorPanelProps {
  cabinetLocation?: string
}

export function ActuatorPanel({ cabinetLocation = 'CAB-A' }: ActuatorPanelProps) {
  const { telemetry, sendActuatorCommand } = useTelemetryWs(cabinetLocation)

  // Local state initialized from telemetry or toggled interactively
  const [peltierActive, setPeltierActive] = useState<boolean>(
    telemetry.actuators?.peltier_active ?? false
  )
  const [ventilationOpen, setVentilationOpen] = useState<boolean>(
    (telemetry.actuators?.ventilation_servo_angle ?? 0) > 0
  )

  const handleTogglePeltier = async () => {
    const nextState = !peltierActive
    setPeltierActive(nextState)
    await sendActuatorCommand({
      peltier_active: nextState,
    })
  }

  const handleToggleVentilation = async () => {
    const nextState = !ventilationOpen
    setVentilationOpen(nextState)
    await sendActuatorCommand({
      ventilation_servo_angle: nextState ? 90 : 0,
    })
  }

  return (
    <div
      data-testid="actuator-panel"
      className="relative flex flex-col rounded-3xl border border-violet-400/20 bg-gradient-to-br from-[#120726]/90 via-[#0a0318]/90 to-[#180a32]/90 p-5 shadow-2xl backdrop-blur-xl"
    >
      {/* Panel Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-400">
            <Cpu className="size-4" />
          </div>
          <div>
            <span className="font-mono text-xs font-bold tracking-wider text-white">
              TWO-WAY ACTUATOR CONTROLS
            </span>
            <p className="text-[10px] font-mono text-violet-300/60">
              BIDIRECTIONAL HARDWARE TELECOMMANDS
            </p>
          </div>
        </div>

        <div
          data-testid="hardware-controls"
          className="flex items-center gap-1.5 rounded-full border border-violet-700/40 bg-violet-950/40 px-2.5 py-0.5 text-[10px] font-mono text-violet-300"
        >
          <span className="size-1.5 rounded-full bg-emerald-400 animate-ping" />
          <span>DOWNLINK READY</span>
        </div>
      </div>

      {/* Actuator Toggles Grid */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {/* 1. Peltier Thermal Cooler */}
        <div className="relative flex flex-col justify-between rounded-2xl border border-violet-800/40 bg-[#14062a]/80 p-4 transition">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <div
                className={`flex size-9 items-center justify-center rounded-xl transition ${
                  peltierActive
                    ? 'bg-cyan-500/20 text-cyan-300 shadow-[0_0_12px_rgba(6,182,212,0.5)]'
                    : 'bg-violet-900/30 text-purple-300/60'
                }`}
              >
                <Snowflake className={`size-5 ${peltierActive ? 'animate-spin' : ''}`} />
              </div>
              <div>
                <h4 className="font-mono text-sm font-bold text-white">Peltier Cooling</h4>
                <p className="text-[10px] font-mono text-purple-300/60">TEC1-12706 Sub-Chamber</p>
              </div>
            </div>

            {/* Live Indicator */}
            <div className="flex items-center gap-1 font-mono text-[10px]">
              {peltierActive ? (
                <span className="flex items-center gap-1 rounded-md bg-emerald-500/20 px-2 py-0.5 font-bold text-emerald-400 ring-1 ring-emerald-500/40">
                  <span className="size-1.5 rounded-full bg-emerald-500 bg-cyan-500" />
                  ACTIVE · ON
                </span>
              ) : (
                <span className="rounded-md bg-zinc-800/40 px-2 py-0.5 text-zinc-400">
                  STANDBY
                </span>
              )}
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between border-t border-violet-900/40 pt-3">
            <span className="font-mono text-[11px] text-purple-200/70">
              {peltierActive ? '12.0V · 4.2A Active' : '0.0V · Inactive'}
            </span>
            <button
              type="button"
              data-testid="toggle-peltier"
              onClick={handleTogglePeltier}
              className={`flex items-center gap-1.5 rounded-xl px-4 py-1.5 font-mono text-xs font-bold transition active:scale-95 ${
                peltierActive
                  ? 'bg-emerald-500 text-black shadow-[0_0_15px_rgba(16,185,129,0.5)] hover:bg-emerald-400'
                  : 'border border-violet-700/60 bg-violet-900/40 text-violet-200 hover:bg-violet-800/50'
              }`}
            >
              <Power className="size-3.5" />
              <span>{peltierActive ? 'Cooling ON' : 'Peltier Power'}</span>
            </button>
          </div>
        </div>

        {/* 2. Ventilation Exhaust Servo */}
        <div className="relative flex flex-col justify-between rounded-2xl border border-violet-800/40 bg-[#14062a]/80 p-4 transition">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <div
                className={`flex size-9 items-center justify-center rounded-xl transition ${
                  ventilationOpen
                    ? 'bg-emerald-500/20 text-emerald-300 shadow-[0_0_12px_rgba(16,185,129,0.5)]'
                    : 'bg-violet-900/30 text-purple-300/60'
                }`}
              >
                <Fan className={`size-5 ${ventilationOpen ? 'animate-spin' : ''}`} />
              </div>
              <div>
                <h4 className="font-mono text-sm font-bold text-white">Ventilation Servo</h4>
                <p className="text-[10px] font-mono text-purple-300/60">MG996R Exhaust Damper</p>
              </div>
            </div>

            {/* Angle Indicator */}
            <div className="flex items-center gap-1 font-mono text-[10px]">
              {ventilationOpen ? (
                <span className="flex items-center gap-1 rounded-md bg-emerald-500/20 px-2 py-0.5 font-bold text-emerald-400 ring-1 ring-emerald-500/40">
                  <Compass className="size-3" />
                  90° · OPEN (Exhaust Active)
                </span>
              ) : (
                <span className="rounded-md bg-zinc-800/40 px-2 py-0.5 text-zinc-400">
                  0° · CLOSED
                </span>
              )}
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between border-t border-violet-900/40 pt-3">
            <span className="font-mono text-[11px] text-purple-200/70">
              {ventilationOpen ? 'Servo Angle: 90° (OPEN)' : 'Servo Angle: 0° (CLOSED)'}
            </span>
            <button
              type="button"
              data-testid="toggle-ventilation"
              onClick={handleToggleVentilation}
              className={`flex items-center gap-1.5 rounded-xl px-4 py-1.5 font-mono text-xs font-bold transition active:scale-95 ${
                ventilationOpen
                  ? 'bg-cyan-500 text-black shadow-[0_0_15px_rgba(6,182,212,0.5)] hover:bg-cyan-400'
                  : 'border border-violet-700/60 bg-violet-900/40 text-violet-200 hover:bg-violet-800/50'
              }`}
            >
              <Fan className="size-3.5" />
              <span>{ventilationOpen ? 'Ventilation OPEN' : 'Ventilation Servo'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
