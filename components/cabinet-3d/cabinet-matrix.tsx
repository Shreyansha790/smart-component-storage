'use client'

import React, { useEffect, useRef, useState, useCallback } from 'react'
import * as THREE from 'three'
import {
  Layers,
  Box,
  RotateCcw,
  Compass,
  Sparkles,
  Maximize2,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  Flame,
  Volume2,
} from 'lucide-react'
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
    partNumber: 'SHT31-DIS-B Temp/Hum',
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
    partNumber: 'ATmega328P-PU DIP',
    batchId: 'BAT-2026-M4',
    shelfLife: '365 days',
    remaining: '85 days',
    degradation: '0.64 (Thermal Drift)',
    quantity: 16,
    temperature: '26.8°C',
    humidity: '49.1%',
    status: 'APPROACHING_LIMIT',
    isLocated: false,
  },
  {
    id: 'ROW-B1',
    slotNumber: 'B1',
    partNumber: 'CC1101 Sub-1GHz RF',
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
    partNumber: 'BME680 Gas Sensor',
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
    partNumber: 'TPS63020 Buck-Boost',
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
    partNumber: 'INA219 Power Monitor',
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

// Helper to generate crisp canvas texture for drawer faceplates
function createDrawerFaceTexture(slot: DrawerSlotInfo) {
  const canvas = document.createElement('canvas')
  canvas.width = 512
  canvas.height = 512
  const ctx = canvas.getContext('2d')
  if (!ctx) return new THREE.CanvasTexture(canvas)

  // Brushed Surgical Silver/White Faceplate Background
  const grad = ctx.createLinearGradient(0, 0, 512, 512)
  grad.addColorStop(0, '#f8fafc')
  grad.addColorStop(0.5, '#e2e8f0')
  grad.addColorStop(1, '#cbd5e1')
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, 512, 512)

  // Subtle brushed metallic horizontal micro-lines
  ctx.strokeStyle = 'rgba(0, 0, 0, 0.04)'
  ctx.lineWidth = 1
  for (let y = 0; y < 512; y += 4) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(512, y)
    ctx.stroke()
  }

  // Inner beveled chamfer border
  ctx.strokeStyle = 'rgba(2, 132, 199, 0.4)'
  ctx.lineWidth = 8
  ctx.strokeRect(16, 16, 480, 480)

  // Corner reinforcement rivets
  ctx.fillStyle = '#94a3b8'
  ;[[32, 32], [480, 32], [32, 480], [480, 480]].forEach(([cx, cy]) => {
    ctx.beginPath()
    ctx.arc(cx, cy, 6, 0, Math.PI * 2)
    ctx.fill()
    ctx.strokeStyle = 'rgba(0,0,0,0.2)'
    ctx.lineWidth = 2
    ctx.stroke()
  })

  // Slot Identifier Badge (e.g. "A1")
  ctx.fillStyle = '#0f172a'
  ctx.font = 'bold 84px "JetBrains Mono", monospace'
  ctx.fillText(slot.slotNumber, 48, 120)

  // Secondary sub-header
  ctx.fillStyle = '#0284c7'
  ctx.font = '700 24px "Plus Jakarta Sans", sans-serif'
  ctx.fillText('BAY LOCATOR', 48, 158)

  // Component Part Number (truncated if needed)
  ctx.fillStyle = '#0f172a'
  ctx.font = 'bold 30px "JetBrains Mono", monospace'
  const partText = slot.partNumber.length > 22 ? slot.partNumber.slice(0, 20) + '...' : slot.partNumber
  ctx.fillText(partText, 48, 380)

  // Stock quantity & batch pill
  ctx.fillStyle = '#475569'
  ctx.font = '600 24px "JetBrains Mono", monospace'
  ctx.fillText(`QTY: ${slot.quantity} PCS | ${slot.batchId}`, 48, 420)

  // Bottom Status Indicator Bar
  let statusColor = '#10b981' // Green
  if (slot.status === 'APPROACHING_LIMIT') statusColor = '#f59e0b' // Amber
  if (slot.status === 'EXPIRED') statusColor = '#f43f5e' // Crimson

  ctx.fillStyle = statusColor
  ctx.fillRect(48, 452, 416, 12)

  const texture = new THREE.CanvasTexture(canvas)
  texture.anisotropy = 8
  return texture
}

// Helper to generate top OLED status display texture
function createOledDisplayTexture(temp: number, humidity: number, status: string) {
  const canvas = document.createElement('canvas')
  canvas.width = 1024
  canvas.height = 128
  const ctx = canvas.getContext('2d')
  if (!ctx) return new THREE.CanvasTexture(canvas)

  // OLED Deep Glass
  ctx.fillStyle = '#05040a'
  ctx.fillRect(0, 0, 1024, 128)

  // Digital scanlines
  ctx.strokeStyle = 'rgba(0, 255, 200, 0.05)'
  ctx.lineWidth = 1
  for (let y = 0; y < 128; y += 4) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(1024, y)
    ctx.stroke()
  }

  // Cyan Digital Text
  ctx.fillStyle = '#06b6d4'
  ctx.font = 'bold 42px "JetBrains Mono", monospace'
  ctx.fillText(`CAB-A // NEMA-4X ENVIRONMENT`, 40, 56)

  ctx.font = 'bold 36px "JetBrains Mono", monospace'
  ctx.fillStyle = '#a855f7'
  ctx.fillText(`TEMP: ${temp.toFixed(1)}°C`, 40, 104)

  ctx.fillStyle = '#38bdf8'
  ctx.fillText(`HUM: ${humidity.toFixed(1)}% RH`, 380, 104)

  ctx.fillStyle = '#10b981'
  ctx.fillText(`STATUS: ${status}`, 740, 104)

  const texture = new THREE.CanvasTexture(canvas)
  texture.anisotropy = 8
  return texture
}

export function CabinetMatrix() {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const { telemetry } = useTelemetryWs('CAB-A')

  const [slots, setSlots] = useState<DrawerSlotInfo[]>(INITIAL_SLOTS)
  const [selectedSlotId, setSelectedSlotId] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'Perspective' | 'Isometric'>('Isometric')
  const [locatedSlotId, setLocatedSlotId] = useState<string | null>(null)
  const [autoRotate, setAutoRotate] = useState<boolean>(false)
  const [hoveredSlotNumber, setHoveredSlotNumber] = useState<string | null>(null)

  // Three.js scene refs
  const sceneRef = useRef<THREE.Scene | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const cabinetGroupRef = useRef<THREE.Group | null>(null)
  const drawersMeshMap = useRef<Map<string, THREE.Group>>(new Map())
  const drawerLedMats = useRef<Map<string, THREE.MeshStandardMaterial>>(new Map())
  const oledMeshRef = useRef<THREE.Mesh | null>(null)
  const targetCameraPos = useRef<THREE.Vector3>(new THREE.Vector3(7.2, 5.5, 7.8))

  // Mouse interaction state for direct 3D raycasting and drag-to-rotate
  const isDragging = useRef(false)
  const previousMousePosition = useRef({ x: 0, y: 0 })
  const rotationDamping = useRef({ x: 0.15, y: -0.45 })
  const raycaster = useRef(new THREE.Raycaster())
  const mouseCoords = useRef(new THREE.Vector2())

  // Initialize Realistic Three.js 3D Environment
  useEffect(() => {
    const canvas = canvasRef.current
    const container = containerRef.current
    if (!canvas || !container) return

    const width = container.clientWidth || 640
    const height = 360

    // 1. Scene & Camera
    const scene = new THREE.Scene()
    sceneRef.current = scene

    const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 1000)
    camera.position.set(7.2, 5.5, 7.8)
    camera.lookAt(0, 0, 0)
    cameraRef.current = camera

    // 2. High-Performance WebGL Renderer with Shadows & Tone Mapping
    const renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
      powerPreference: 'high-performance',
    })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.2
    rendererRef.current = renderer

    // 3. Multi-Point Studio Lighting (Hyper-Realistic Cleanroom Industrial Rig)
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.6) // Crisp white laboratory ambient
    scene.add(ambientLight)

    // Key Light (Warm Sunlight Angle casting soft shadows)
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.0)
    keyLight.position.set(8, 12, 9)
    keyLight.castShadow = true
    keyLight.shadow.mapSize.width = 1024
    keyLight.shadow.mapSize.height = 1024
    keyLight.shadow.camera.near = 1
    keyLight.shadow.camera.far = 30
    keyLight.shadow.bias = -0.0005
    scene.add(keyLight)

    // Cool Sky Fill Light (Sharp cleanroom edge highlights)
    const rimLight = new THREE.DirectionalLight(0x0284c7, 1.2)
    rimLight.position.set(-9, 4, -6)
    scene.add(rimLight)

    // Subtle Ground Ambient Bounce Light
    const floorGlow = new THREE.PointLight(0x38bdf8, 1.2, 15)
    floorGlow.position.set(0, -3.5, 2)
    scene.add(floorGlow)

    // Overhead White Inspection Light
    const topLight = new THREE.SpotLight(0xffffff, 2.2, 20, Math.PI / 4, 0.3)
    topLight.position.set(0, 7, 3)
    scene.add(topLight)

    // 4. Cabinet Master Group (Enables 360-degree interactive rotation)
    const cabinetGroup = new THREE.Group()
    cabinetGroupRef.current = cabinetGroup
    cabinetGroup.rotation.x = rotationDamping.current.x
    cabinetGroup.rotation.y = rotationDamping.current.y
    scene.add(cabinetGroup)

    // 5. Floor Shadow Plane & Circular Ground Contact
    const groundGeo = new THREE.PlaneGeometry(24, 24)
    const groundMat = new THREE.MeshStandardMaterial({
      color: 0xe2e8f0,
      roughness: 0.9,
      metalness: 0.05,
    })
    const groundMesh = new THREE.Mesh(groundGeo, groundMat)
    groundMesh.rotation.x = -Math.PI / 2
    groundMesh.position.y = -2.6
    groundMesh.receiveShadow = true
    cabinetGroup.add(groundMesh)

    // Ground Grid Wireframe (Cleanroom precision grid)
    const gridHelper = new THREE.GridHelper(16, 24, 0x0284c7, 0xcbd5e1)
    gridHelper.position.y = -2.59
    cabinetGroup.add(gridHelper)

    // 6. Realistic Industrial Chassis Enclosure
    // Outer Armor Shell (Surgical Powder-Coated Cleanroom Enclosure)
    const chassisGeo = new THREE.BoxGeometry(8.0, 4.8, 3.6)
    const chassisMat = new THREE.MeshStandardMaterial({
      color: 0x334155, // Clean Slate Armor Enclosure
      metalness: 0.75,
      roughness: 0.25,
    })
    const chassis = new THREE.Mesh(chassisGeo, chassisMat)
    chassis.castShadow = true
    chassis.receiveShadow = true
    cabinetGroup.add(chassis)

    // Beveled Edge Highlight Frame
    const edges = new THREE.EdgesGeometry(chassisGeo)
    const edgeLine = new THREE.LineSegments(
      edges,
      new THREE.LineBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.4 })
    )
    cabinetGroup.add(edgeLine)

    // Left and Right 19" Server Rack Rails (Chromed Extrusions)
    ;[-4.08, 4.08].forEach((xPos) => {
      const railGeo = new THREE.BoxGeometry(0.18, 4.8, 0.4)
      const railMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        metalness: 0.95,
        roughness: 0.15,
      })
      const rail = new THREE.Mesh(railGeo, railMat)
      rail.position.set(xPos, 0, 1.7)
      cabinetGroup.add(rail)

      // Hex mounting screws down the rail
      ;[-1.8, -0.9, 0, 0.9, 1.8].forEach((yPos) => {
        const screwGeo = new THREE.CylinderGeometry(0.04, 0.04, 0.05, 6)
        const screwMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.9 })
        const screw = new THREE.Mesh(screwGeo, screwMat)
        screw.rotation.x = Math.PI / 2
        screw.position.set(xPos, yPos, 1.91)
        cabinetGroup.add(screw)
      })
    })

    // Top Digital OLED Telemetry Banner
    const oledGeo = new THREE.PlaneGeometry(7.4, 0.5)
    const initialOledTex = createOledDisplayTexture(
      telemetry.smoothed_temp || 24.2,
      telemetry.smoothed_humidity || 44.8,
      'NOMINAL'
    )
    const oledMat = new THREE.MeshBasicMaterial({
      map: initialOledTex,
      transparent: true,
    })
    const oledMesh = new THREE.Mesh(oledGeo, oledMat)
    oledMesh.position.set(0, 2.15, 1.81)
    cabinetGroup.add(oledMesh)
    oledMeshRef.current = oledMesh

    // 7. High-Fidelity Drawers (2 Rows × 4 Cols)
    const rows = ['A', 'B']
    const cols = [1, 2, 3, 4]
    const drawerBodyGeo = new THREE.BoxGeometry(1.68, 1.72, 3.2)
    const drawerInteriorGeo = new THREE.BoxGeometry(1.5, 1.4, 2.8)

    drawersMeshMap.current.clear()
    drawerLedMats.current.clear()

    rows.forEach((row, rIdx) => {
      cols.forEach((col, cIdx) => {
        const slotKey = `${row}${col}`
        const slotData = INITIAL_SLOTS.find((s) => s.slotNumber === slotKey) || INITIAL_SLOTS[0]

        // Group holding drawer body and all child meshes
        const drawerGroup = new THREE.Group()
        const x = (cIdx - 1.5) * 1.85
        const y = (0.5 - rIdx) * 1.82 - 0.2
        const z = 0.2

        drawerGroup.position.set(x, y, z)
        drawerGroup.userData = { slotKey, slotId: `ROW-${slotKey}`, slotData }

        // Main Drawer Outer Casing
        const faceTexture = createDrawerFaceTexture(slotData)
        const drawerMaterials = [
          new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.8, roughness: 0.3 }), // Right
          new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.8, roughness: 0.3 }), // Left
          new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.8, roughness: 0.3 }), // Top
          new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.8, roughness: 0.3 }), // Bottom
          new THREE.MeshStandardMaterial({
            map: faceTexture,
            metalness: 0.6,
            roughness: 0.25,
            bumpScale: 0.05,
          }), // Front Face
          new THREE.MeshStandardMaterial({ color: 0x1e293b, metalness: 0.8, roughness: 0.4 }), // Back
        ]

        const drawerBox = new THREE.Mesh(drawerBodyGeo, drawerMaterials)
        drawerBox.castShadow = true
        drawerBox.receiveShadow = true
        drawerBox.userData = { isClickable: true, slotKey, slotId: `ROW-${slotKey}` }
        drawerGroup.add(drawerBox)

        // Internal ESD Foam Tray (Revealed when pulled open)
        const foamMat = new THREE.MeshStandardMaterial({
          color: 0x09080e,
          roughness: 0.95,
          metalness: 0.05,
        })
        const foamTray = new THREE.Mesh(drawerInteriorGeo, foamMat)
        foamTray.position.set(0, -0.1, -0.1)
        drawerGroup.add(foamTray)

        // 3D Electronic Components Inside Drawer Tray (Reels, IC chips)
        const icGeo = new THREE.BoxGeometry(0.35, 0.08, 0.35)
        const icMat = new THREE.MeshStandardMaterial({
          color: 0x111827,
          metalness: 0.9,
          roughness: 0.2,
        })
        ;[-0.4, 0, 0.4].forEach((icX) => {
          ;[-0.6, 0, 0.6].forEach((icZ) => {
            const ic = new THREE.Mesh(icGeo, icMat)
            ic.position.set(icX, 0.65, icZ)
            drawerGroup.add(ic)

            // Shiny central chip die
            const dieGeo = new THREE.BoxGeometry(0.15, 0.09, 0.15)
            const dieMat = new THREE.MeshStandardMaterial({ color: 0xd97706, metalness: 0.95 })
            const die = new THREE.Mesh(dieGeo, dieMat)
            die.position.set(icX, 0.66, icZ)
            drawerGroup.add(die)
          })
        })

        // Heavy-Duty Extruded Chrome Drawer Handle
        const handleBarGeo = new THREE.BoxGeometry(0.9, 0.14, 0.14)
        const handleMat = new THREE.MeshStandardMaterial({
          color: 0xf1f5f9,
          metalness: 0.95,
          roughness: 0.1,
        })
        const handle = new THREE.Mesh(handleBarGeo, handleMat)
        handle.position.set(0, -0.25, 1.68)
        handle.castShadow = true
        handle.userData = { isClickable: true, slotKey, slotId: `ROW-${slotKey}` }
        drawerGroup.add(handle)

        // Status Indicator LED Jewel (Top of drawer)
        let ledColor = 0x10b981
        if (slotData.status === 'APPROACHING_LIMIT') ledColor = 0xf59e0b
        if (slotData.status === 'EXPIRED') ledColor = 0xf43f5e

        const ledGeo = new THREE.BoxGeometry(0.3, 0.06, 0.08)
        const ledMat = new THREE.MeshStandardMaterial({
          color: ledColor,
          emissive: ledColor,
          emissiveIntensity: 0.8,
          roughness: 0.2,
        })
        const ledMesh = new THREE.Mesh(ledGeo, ledMat)
        ledMesh.position.set(0, 0.68, 1.62)
        drawerGroup.add(ledMesh)
        drawerLedMats.current.set(slotKey, ledMat)

        // Point Light Illuminating Drawer Contents when Opened
        const interiorSpot = new THREE.PointLight(0xfffbeb, 0, 2.5)
        interiorSpot.position.set(0, 0.8, 0.5)
        drawerGroup.add(interiorSpot)
        drawerGroup.userData.interiorSpot = interiorSpot

        cabinetGroup.add(drawerGroup)
        drawersMeshMap.current.set(slotKey, drawerGroup)
      })
    })

    // 8. Interactive Raycasting & Drag Events
    const getPointerPos = (e: MouseEvent | TouchEvent) => {
      const rect = canvas.getBoundingClientRect()
      const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX
      const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY
      return {
        x: ((clientX - rect.left) / rect.width) * 2 - 1,
        y: -((clientY - rect.top) / rect.height) * 2 + 1,
        clientX,
        clientY,
      }
    }

    const onMouseDown = (e: MouseEvent) => {
      isDragging.current = true
      previousMousePosition.current = { x: e.clientX, y: e.clientY }
    }

    const onMouseMove = (e: MouseEvent) => {
      const pos = getPointerPos(e)
      mouseCoords.current.set(pos.x, pos.y)

      if (isDragging.current && cabinetGroupRef.current) {
        const deltaX = e.clientX - previousMousePosition.current.x
        const deltaY = e.clientY - previousMousePosition.current.y
        cabinetGroupRef.current.rotation.y += deltaX * 0.008
        cabinetGroupRef.current.rotation.x += deltaY * 0.008
        // Clamp vertical tilt
        cabinetGroupRef.current.rotation.x = Math.max(
          -0.4,
          Math.min(0.6, cabinetGroupRef.current.rotation.x)
        )
        previousMousePosition.current = { x: e.clientX, y: e.clientY }
      }

      // Hover Raycasting
      if (cameraRef.current && sceneRef.current) {
        raycaster.current.setFromCamera(mouseCoords.current, cameraRef.current)
        const intersects = raycaster.current.intersectObjects(sceneRef.current.children, true)
        const hitDrawer = intersects.find((hit) => hit.object.userData?.isClickable)
        if (hitDrawer) {
          canvas.style.cursor = 'pointer'
          setHoveredSlotNumber(hitDrawer.object.userData.slotKey)
        } else {
          canvas.style.cursor = isDragging.current ? 'grabbing' : 'grab'
          setHoveredSlotNumber(null)
        }
      }
    }

    const onMouseUp = (e: MouseEvent) => {
      const delta =
        Math.abs(e.clientX - previousMousePosition.current.x) +
        Math.abs(e.clientY - previousMousePosition.current.y)
      isDragging.current = false

      // If clicked without significant drag, trigger drawer select
      if (delta < 5 && cameraRef.current && sceneRef.current) {
        const pos = getPointerPos(e)
        mouseCoords.current.set(pos.x, pos.y)
        raycaster.current.setFromCamera(mouseCoords.current, cameraRef.current)
        const intersects = raycaster.current.intersectObjects(sceneRef.current.children, true)
        const hitDrawer = intersects.find((hit) => hit.object.userData?.isClickable)
        if (hitDrawer) {
          const slotId = hitDrawer.object.userData.slotId
          setSelectedSlotId(slotId)
        }
      }
    }

    canvas.addEventListener('mousedown', onMouseDown)
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)

    // 9. Animation Render Loop (Physics & Slide Lerp)
    let animId: number
    const clock = new THREE.Clock()

    const animate = () => {
      animId = requestAnimationFrame(animate)
      const elapsedTime = clock.getElapsedTime()

      // Turntable Auto-Rotation Mode
      if (autoRotate && cabinetGroupRef.current && !isDragging.current) {
        cabinetGroupRef.current.rotation.y += 0.005
      }

      // Smooth Camera Lerping toward target position
      if (cameraRef.current) {
        cameraRef.current.position.lerp(targetCameraPos.current, 0.05)
        cameraRef.current.lookAt(0, 0, 0)
      }

      // Physical Drawer Slide Animation & Interior Light
      drawersMeshMap.current.forEach((group, key) => {
        const isSelected = selectedSlotId === `ROW-${key}` || selectedSlotId === key
        const targetZ = isSelected ? 1.6 : 0.2
        group.position.z += (targetZ - group.position.z) * 0.12

        // Toggle interior light when pulled open
        const spot = group.userData.interiorSpot as THREE.PointLight | undefined
        if (spot) {
          spot.intensity = THREE.MathUtils.lerp(spot.intensity, isSelected ? 3.5 : 0, 0.1)
        }
      })

      // Pulsing LED Beacon on Located Slot
      if (locatedSlotId) {
        const key = locatedSlotId.replace('ROW-', '')
        const mat = drawerLedMats.current.get(key)
        if (mat) {
          mat.emissive.setHex(0x06b6d4) // Bright Cyan beacon
          mat.emissiveIntensity = 1.0 + Math.sin(elapsedTime * 8) * 0.8
        }
      }

      renderer.render(scene, camera)
    }
    animate()

    // Resize Handler
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
      canvas.removeEventListener('mousedown', onMouseDown)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      window.removeEventListener('resize', handleResize)
      renderer.dispose()
      chassisGeo.dispose()
      drawerBodyGeo.dispose()
    }
  }, [selectedSlotId, autoRotate, locatedSlotId, telemetry.smoothed_temp, telemetry.smoothed_humidity])

  // Camera presets
  const handleToggleView = () => {
    if (viewMode === 'Perspective') {
      setViewMode('Isometric')
      targetCameraPos.current.set(7.2, 5.5, 7.8)
    } else {
      setViewMode('Perspective')
      targetCameraPos.current.set(0, 1.2, 8.8)
    }
  }

  const handleResetCamera = () => {
    if (cabinetGroupRef.current) {
      cabinetGroupRef.current.rotation.x = 0.15
      cabinetGroupRef.current.rotation.y = -0.45
    }
    targetCameraPos.current.set(7.2, 5.5, 7.8)
    setViewMode('Isometric')
  }

  const handleSlotClick = (slot: DrawerSlotInfo) => {
    setSelectedSlotId(slot.id)
  }

  const handleLocateSlot = (slotId: string) => {
    setLocatedSlotId(slotId)
    setSlots((prev) =>
      prev.map((s) => ({
        ...s,
        isLocated: s.id === slotId,
      }))
    )
    // Focus camera on target drawer
    setSelectedSlotId(slotId)
  }

  const selectedSlot = slots.find((s) => s.id === selectedSlotId) || null

  const handleDispatchSlot = (slotId: string, amount: number) => {
    setSlots((prev) =>
      prev.map((s) => (s.id === slotId ? { ...s, quantity: Math.max(0, s.quantity - amount) } : s))
    )
  }

  return (
    <div
      data-testid="cabinet-matrix"
      ref={containerRef}
      className="relative flex flex-col rounded-3xl border border-slate-200/80 bg-white p-5 shadow-sm backdrop-blur-2xl"
    >
      {/* 3D Matrix Header Controls */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 text-white shadow-md shadow-sky-500/20">
            <Box className="size-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold tracking-wider text-slate-900">
                SMART CABINET 3D MATRIX (CAB-A)
              </span>
              <span className="rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 font-mono text-[10px] text-emerald-700 font-semibold">
                PHOTOREALISTIC PBR
              </span>
            </div>
            <p className="text-[11px] font-mono text-slate-500">
              PHYSICAL ENCLOSURE & INTERACTIVE TELESCOPIC DRAWERS
            </p>
          </div>
        </div>

        {/* Viewport Control Buttons */}
        <div className="flex items-center gap-2 font-mono text-xs">
          <button
            type="button"
            data-testid="view-toggle"
            onClick={handleToggleView}
            className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 font-semibold text-slate-700 transition hover:bg-slate-100 hover:text-slate-900 active:scale-95 shadow-sm"
          >
            <Layers className="size-3.5 text-sky-600" />
            <span>{viewMode === 'Perspective' ? 'Isometric (3D)' : 'Perspective (3D)'}</span>
          </button>

          <button
            type="button"
            onClick={() => setAutoRotate(!autoRotate)}
            className={`flex items-center gap-1.5 rounded-xl border px-3 py-1.5 font-semibold transition active:scale-95 shadow-sm ${
              autoRotate
                ? 'border-sky-300 bg-sky-50 text-sky-700 font-bold'
                : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'
            }`}
          >
            <Compass className="size-3.5 text-sky-600" />
            <span>{autoRotate ? 'Turntable: ON' : 'Turntable'}</span>
          </button>

          <button
            type="button"
            onClick={handleResetCamera}
            title="Reset Camera Orientation"
            className="flex size-8 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 shadow-sm"
          >
            <RotateCcw className="size-3.5" />
          </button>
        </div>
      </div>

      {/* 3D WebGL Canvas Viewport */}
      <div className="relative h-80 w-full overflow-hidden rounded-2xl border border-slate-200 bg-radial from-slate-100 to-slate-200/60 shadow-inner">
        <canvas
          ref={canvasRef}
          data-testid="cabinet-3d-view"
          className="block h-full w-full cursor-grab active:cursor-grabbing"
        />

        {/* HUD Info Badges */}
        <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-2 font-mono text-[10px]">
          <span className="rounded-md border border-slate-300 bg-white/90 px-2 py-0.5 text-slate-700 shadow-sm backdrop-blur-md font-semibold">
            PBR CHASSIS & NEMA-4X
          </span>
          <span className="rounded-md border border-sky-300 bg-sky-50/90 px-2 py-0.5 text-sky-700 shadow-sm backdrop-blur-md font-semibold">
            CAMERA: {viewMode.toUpperCase()}
          </span>
          {hoveredSlotNumber && (
            <span className="rounded-md border border-amber-300 bg-amber-50/90 px-2 py-0.5 text-amber-800 animate-pulse shadow-sm backdrop-blur-md font-semibold">
              CLICK TO PULL DRAWER {hoveredSlotNumber}
            </span>
          )}
        </div>

        {/* Tactile Hint Overlay */}
        <div className="pointer-events-none absolute bottom-3 right-3 rounded-lg border border-slate-200 bg-white/80 px-2.5 py-1 font-mono text-[10px] text-slate-500 backdrop-blur-md shadow-sm">
          Drag to orbit 360° • Click any 3D drawer to open
        </div>
      </div>

      {/* Interactive Slot Grid Layout (8 Physical Slots) */}
      <div className="mt-5 flex flex-col gap-3">
        <div className="flex items-center justify-between text-[11px] font-mono text-slate-500">
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
                  isSelected
                    ? 'ring-2 ring-sky-500 bg-sky-50 -translate-y-1 shadow-md shadow-sky-500/15'
                    : 'bg-white hover:bg-slate-50 hover:-translate-y-0.5 shadow-sm'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-black text-slate-900">{slot.slotNumber}</span>
                  <span
                    className={`rounded-full px-2 py-0.5 font-mono text-[9px] font-bold border ${
                      isExpired
                        ? 'border-rose-200 bg-rose-50 text-rose-700'
                        : isWarning
                        ? 'border-amber-200 bg-amber-50 text-amber-700'
                        : 'border-emerald-200 bg-emerald-50 text-emerald-700'
                    }`}
                  >
                    {slot.status}
                  </span>
                </div>

                <div className="my-2">
                  <p className="truncate font-mono text-xs font-bold text-slate-900">{slot.partNumber}</p>
                  <p className="font-mono text-[10px] text-slate-500">
                    {slot.quantity} units • {slot.remaining}
                  </p>
                </div>

                <div className="flex items-center justify-between border-t border-slate-100 pt-1.5 font-mono text-[10px] text-slate-400">
                  <span>{slot.temperature}</span>
                  <span>{slot.humidity}</span>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Drawer Inspection Modal (Renders when a drawer is selected) */}
      {selectedSlot && (
        <div className="mt-5">
          <DrawerInspection
            slot={selectedSlot}
            onClose={() => setSelectedSlotId(null)}
            onLocate={handleLocateSlot}
            onDispatch={handleDispatchSlot}
          />
        </div>
      )}
    </div>
  )
}
