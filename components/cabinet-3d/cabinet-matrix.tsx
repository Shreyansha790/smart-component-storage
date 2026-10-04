'use client'

import React, { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { Eye, Layers, Sparkles, Box } from 'lucide-react'
import { DrawerInspection, type DrawerSlotInfo } from './drawer-inspection'
import { useTelemetryWs } from '@/lib/use-telemetry-ws'

const INITIAL_SLOTS: DrawerSlotInfo[] = [
  {
    id: 'ROW-A1',
    slotNumber: 'A1',
    partNumber: 'ESP32-WROOM-32D',
    batchId: 'BAT-2026-X8',
    shelfLife: '365 days',
    remaining: '210 days',
    degradation: '0.28 (Kinetic Arrhenius)',
    quantity: 24,
    temperature: '24.2°C',
    humidity: '44.8%',
    status: 'OPTIMAL',
    isLocated: false,
  },
  {
    id: 'ROW-A2',
    slotNumber: 'A2',
    partNumber: 'STM32F401RE MCU',
    batchId: 'BAT-2025-L9',
    shelfLife: '180 days',
    remaining: '14 days',
    degradation: '0.88 (Accelerated Excursion)',
    quantity: 8,
    temperature: '28.5°C',
    humidity: '56.2%',
    status: 'EXPIRED',
    isLocated: false,
  },
  {
    id: 'ROW-A3',
    slotNumber: 'A3',
    partNumber: 'SHT31-DIS-B Temp/Hum Sensor',
    batchId: 'BAT-2026-C2',
    shelfLife: '730 days',
    remaining: '610 days',
    degradation: '0.12 (Normal Nominal)',
    quantity: 45,
    temperature: '24.1°C',
    humidity: '45.0%',
    status: 'OPTIMAL',
    isLocated: false,
  },
  {
    id: 'ROW-A4',
    slotNumber: 'A4',
    partNumber: 'ATmega328P-PU DIP-28',
    batchId: 'BAT-2026-M4',
    shelfLife: '365 days',
    remaining: '85 days',
    degradation: '0.64 (Moderate Thermal Drift)',
    quantity: 16,
    temperature: '26.8°C',
    humidity: '49.1%',
    status: 'APPROACHING_LIMIT',
    isLocated: false,
  },
  {
    id: 'ROW-B1',
    slotNumber: 'B1',
    partNumber: 'CC1101 Sub-1GHz Transceiver',
    batchId: 'BAT-2026-R1',
    shelfLife: '540 days',
    remaining: '420 days',
    degradation: '0.18 (Normal Nominal)',
    quantity: 30,
    temperature: '23.9°C',
    humidity: '44.2%',
    status: 'OPTIMAL',
    isLocated: false,
  },
  {
    id: 'ROW-B2',
    slotNumber: 'B2',
    partNumber: 'BME680 Environmental Gas',
    batchId: 'BAT-2026-G7',
    shelfLife: '365 days',
    remaining: '95 days',
    degradation: '0.58 (Elevated Humidity)',
    quantity: 12,
    temperature: '26.2°C',
    humidity: '52.0%',
    status: 'APPROACHING_LIMIT',
    isLocated: false,
  },
  {
    id: 'ROW-B3',
    slotNumber: 'B3',
    partNumber: 'TPS63020 Buck-Boost Reg',
    batchId: 'BAT-2026-P3',
    shelfLife: '730 days',
    remaining: '680 days',
    degradation: '0.08 (Normal Nominal)',
    quantity: 60,
    temperature: '23.8°C',
    humidity: '43.9%',
    status: 'OPTIMAL',
    isLocated: false,
  },
  {
    id: 'ROW-B4',
    slotNumber: 'B4',
    partNumber: 'INA219 Current/Power Mon',
    batchId: 'BAT-2026-I2',
    shelfLife: '540 days',
    remaining: '390 days',
    degradation: '0.22 (Normal Nominal)',
    quantity: 18,
    temperature: '24.0°C',
    humidity: '44.5%',
    status: 'OPTIMAL',
    isLocated: false,
  },
]

export function CabinetMatrix() {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const { telemetry } = useTelemetryWs('CAB-A')

  const [slots, setSlots] = useState<DrawerSlotInfo[]>(INITIAL_SLOTS)
  const [selectedSlotId, setSelectedSlotId] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'Perspective' | 'Isometric'>('Perspective')
  const [locatedSlotId, setLocatedSlotId] = useState<string | null>(null)

  // Three.js scene refs
  const sceneRef = useRef<THREE.Scene | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const drawersMeshMap = useRef<Map<string, THREE.Mesh>>(new Map())
  const targetCameraPos = useRef<THREE.Vector3>(new THREE.Vector3(0, 1.5, 9))

  // Initialize Three.js Physical 3D Cabinet Matrix
  useEffect(() => {
    const canvas = canvasRef.current
    const container = containerRef.current
    if (!canvas || !container) return

    const width = container.clientWidth || 640
    const height = 320

    // 1. Scene & Camera
    const scene = new THREE.Scene()
    sceneRef.current = scene

    const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 1000)
    camera.position.set(0, 1.5, 9)
    camera.lookAt(0, 0, 0)
    cameraRef.current = camera

    // 2. WebGL Renderer
    const renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
      powerPreference: 'high-performance',
    })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    rendererRef.current = renderer

    // 3. Lighting (Cyber Industrial Aesthetic)
    const ambientLight = new THREE.AmbientLight(0x7c3aed, 0.8)
    scene.add(ambientLight)

    const keyLight = new THREE.DirectionalLight(0xd946ef, 1.5)
    keyLight.position.set(5, 8, 7)
    scene.add(keyLight)

    const fillLight = new THREE.DirectionalLight(0x06b6d4, 1.2)
    fillLight.position.set(-6, -2, 5)
    scene.add(fillLight)

    const topSpot = new THREE.PointLight(0xc084fc, 2, 20)
    topSpot.position.set(0, 4, 3)
    scene.add(topSpot)

    // 4. Cabinet Enclosure Chassis (Cyber Titanium Outer Shell)
    const chassisGeo = new THREE.BoxGeometry(7.6, 4.4, 3.2)
    const chassisMat = new THREE.MeshStandardMaterial({
      color: 0x0f0724,
      metalness: 0.85,
      roughness: 0.25,
      wireframe: false,
    })
    const chassis = new THREE.Mesh(chassisGeo, chassisMat)
    scene.add(chassis)

    // Neon edge highlight wireframe frame
    const edges = new THREE.EdgesGeometry(chassisGeo)
    const edgeLine = new THREE.LineSegments(
      edges,
      new THREE.LineBasicMaterial({ color: 0x9333ea, transparent: true, opacity: 0.6 })
    )
    scene.add(edgeLine)

    // 5. Drawers (2 Rows x 4 Cols)
    const rows = ['A', 'B']
    const cols = [1, 2, 3, 4]
    const drawerGeo = new THREE.BoxGeometry(1.6, 1.6, 2.8)

    drawersMeshMap.current.clear()

    rows.forEach((row, rIdx) => {
      cols.forEach((col, cIdx) => {
        const slotKey = `${row}${col}`
        const x = (cIdx - 1.5) * 1.8
        const y = (1 - rIdx - 0.5) * 1.9
        const z = 0.2

        const drawerMat = new THREE.MeshStandardMaterial({
          color: 0x1d0a3d,
          metalness: 0.7,
          roughness: 0.35,
        })
        const drawerMesh = new THREE.Mesh(drawerGeo, drawerMat)
        drawerMesh.position.set(x, y, z)
        scene.add(drawerMesh)

        // Add handle bar
        const handleGeo = new THREE.BoxGeometry(0.8, 0.12, 0.1)
        const handleMat = new THREE.MeshStandardMaterial({
          color: 0xe879f9,
          emissive: 0xa855f7,
          emissiveIntensity: 0.5,
        })
        const handleMesh = new THREE.Mesh(handleGeo, handleMat)
        handleMesh.position.set(0, 0, 1.45)
        drawerMesh.add(handleMesh)

        drawersMeshMap.current.set(slotKey, drawerMesh)
      })
    })

    // 6. Animation Loop
    let animId: number
    const animate = () => {
      animId = requestAnimationFrame(animate)

      // Smooth camera interpolation towards target
      if (cameraRef.current) {
        cameraRef.current.position.lerp(targetCameraPos.current, 0.05)
        cameraRef.current.lookAt(0, 0, 0)
      }

      // Smooth drawer slide animation
      drawersMeshMap.current.forEach((mesh, key) => {
        const isSelected = selectedSlotId === `ROW-${key}` || selectedSlotId === key
        const targetZ = isSelected ? 1.4 : 0.2
        mesh.position.z += (targetZ - mesh.position.z) * 0.1
      })

      renderer.render(scene, camera)
    }
    animate()

    // Resize handler
    const handleResize = () => {
      if (!container || !renderer || !camera) return
      const w = container.clientWidth
      camera.aspect = w / height
      camera.updateProjectionMatrix()
      renderer.setSize(w, height)
    }
    window.addEventListener('resize', handleResize)

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', handleResize)
      renderer.dispose()
      chassisGeo.dispose()
      drawerGeo.dispose()
    }
  }, [selectedSlotId])

  // Handle Perspective / Isometric View Toggle
  const handleToggleView = () => {
    if (viewMode === 'Perspective') {
      setViewMode('Isometric')
      // Angled isometric camera view
      targetCameraPos.current.set(7.5, 6.0, 7.5)
    } else {
      setViewMode('Perspective')
      // Front perspective view
      targetCameraPos.current.set(0, 1.5, 9.0)
    }
  }

  // Handle Slot Click
  const handleSlotClick = (slot: DrawerSlotInfo) => {
    setSelectedSlotId(slot.id)
  }

  // Handle Slot Locator Trigger
  const handleLocateSlot = (slotId: string) => {
    setLocatedSlotId(slotId)
    setSlots((prev) =>
      prev.map((s) => ({
        ...s,
        isLocated: s.id === slotId,
      }))
    )
  }

  const selectedSlot = slots.find((s) => s.id === selectedSlotId) || null

  return (
    <div
      data-testid="cabinet-matrix"
      ref={containerRef}
      className="relative flex flex-col rounded-3xl border border-violet-400/20 bg-gradient-to-br from-[#120726]/90 via-[#0a0318]/90 to-[#180a32]/90 p-5 shadow-2xl backdrop-blur-xl"
    >
      {/* 3D Matrix Header Controls */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-lg bg-fuchsia-500/15 text-fuchsia-400">
            <Box className="size-4" />
          </div>
          <div>
            <span className="font-mono text-xs font-bold tracking-wider text-white">
              SMART CABINET 3D MATRIX (CAB-A)
            </span>
            <p className="text-[10px] font-mono text-violet-300/60">
              PHYSICAL ENCLOSURE & SLOT TELEMETRY
            </p>
          </div>
        </div>

        {/* 3D Perspective / Isometric Mode Toggle Button */}
        <button
          type="button"
          data-testid="view-toggle"
          onClick={handleToggleView}
          className="flex items-center gap-2 rounded-xl border border-violet-700/50 bg-violet-950/60 px-3 py-1.5 font-mono text-xs font-bold text-violet-200 transition hover:border-violet-400 hover:bg-violet-900/60 hover:text-white active:scale-95 shadow-md"
        >
          <Layers className="size-3.5 text-fuchsia-400" />
          <span>{viewMode === 'Perspective' ? 'Isometric View (3D)' : 'Perspective (3D)'}</span>
        </button>
      </div>

      {/* 3D WebGL Canvas Viewport */}
      <div className="relative h-64 w-full overflow-hidden rounded-2xl border border-violet-900/40 bg-[#070114]/90 shadow-inner">
        <canvas
          ref={canvasRef}
          data-testid="cabinet-3d-view"
          className="block h-full w-full"
        />

        {/* Overlay Badges */}
        <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-2 font-mono text-[10px]">
          <span className="rounded-md border border-fuchsia-500/30 bg-fuchsia-950/40 px-2 py-0.5 text-fuchsia-300">
            THREE.JS WEBGL RENDERER
          </span>
          <span className="rounded-md border border-cyan-500/30 bg-cyan-950/40 px-2 py-0.5 text-cyan-300">
            CAMERA: {viewMode.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Interactive Slot Grid Layout (8 Physical Slots) */}
      <div className="mt-5 flex flex-col gap-3">
        <div className="flex items-center justify-between text-[11px] font-mono text-purple-300/70">
          <span>INTERACTIVE SLOTS & PICK-AND-PLACE STATUS</span>
          <span>CLICK TO INSPECT DRAWER</span>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {slots.map((slot) => {
            const isSelected = selectedSlotId === slot.id
            const isLocated = locatedSlotId === slot.id || slot.isLocated
            const isExpired = slot.status === 'EXPIRED'
            const isWarning = slot.status === 'APPROACHING_LIMIT'
            const isOptimal = slot.status === 'OPTIMAL'

            // Glow and status border classes matching E2E test specs exactly
            const statusClass = isExpired
              ? 'border-rose-500 glow-expired status-critical'
              : isWarning
              ? 'border-amber-500 glow-warning status-warning'
              : 'border-emerald-500 glow-optimal status-optimal'

            return (
              <button
                key={slot.id}
                type="button"
                data-testid={`slot-${slot.slotNumber}`}
                data-slot-id={slot.id}
                data-slot={slot.slotNumber}
                data-status={slot.status}
                data-located={isLocated ? 'true' : 'false'}
                onClick={() => handleSlotClick(slot)}
                className={`cabinet-slot group relative flex flex-col justify-between rounded-2xl border p-3.5 text-left transition-all duration-200 outline-none ${statusClass} ${
                  isSelected ? 'ring-2 ring-fuchsia-400 ring-offset-2 ring-offset-[#120726]' : ''
                } ${
                  isLocated
                    ? 'animate-pulse glow-active ring-emerald-400 ring-2 shadow-[0_0_20px_rgba(16,185,129,0.7)]'
                    : 'bg-[#15062c]/80 hover:bg-[#1f0940]'
                }`}
              >
                {/* Slot Top Header */}
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-white group-hover:text-fuchsia-300">
                    SLOT {slot.slotNumber}
                  </span>
                  <span
                    className={`size-2 rounded-full ${
                      isExpired
                        ? 'bg-rose-500 shadow-[0_0_8px_#f43f5e]'
                        : isWarning
                        ? 'bg-amber-400 shadow-[0_0_8px_#fbbf24]'
                        : 'bg-emerald-400 shadow-[0_0_8px_#34d399]'
                    }`}
                  />
                </div>

                {/* Component Info */}
                <div className="my-2 flex flex-col font-mono">
                  <span className="truncate text-xs font-bold text-purple-100">
                    {slot.partNumber}
                  </span>
                  <span className="text-[10px] text-purple-300/60">
                    {slot.batchId} · {slot.quantity} pcs
                  </span>
                </div>

                {/* Telemetry Reading Displayed on Slot */}
                <div className="flex items-center justify-between border-t border-violet-900/40 pt-2 font-mono text-[10px]">
                  <span className="text-purple-300/70">{slot.temperature}</span>
                  <span
                    className={
                      isExpired
                        ? 'text-rose-400 font-bold'
                        : isWarning
                        ? 'text-amber-300'
                        : 'text-emerald-300'
                    }
                  >
                    {slot.remaining}
                  </span>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Pull-Out Drawer Inspection Modal/Card */}
      {selectedSlot && (
        <div className="mt-5">
          <DrawerInspection
            slot={selectedSlot}
            onClose={() => setSelectedSlotId(null)}
            onLocate={handleLocateSlot}
          />
        </div>
      )}
    </div>
  )
}
