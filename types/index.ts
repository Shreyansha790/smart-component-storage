export type ComponentCategory =
  | "Microcontrollers"
  | "Sensors"
  | "Resistors"
  | "Capacitors"
  | "LEDs"
  | "Wireless Modules"
  | "Voltage Regulators"
  | "Transistors"

export interface Component {
  id: string
  name: string
  category: ComponentCategory
  quantity: number
  minStock: number
  cabinet: string
  shelf: string
  slot: string
  description: string
  updatedAgo: string
  lastActivity: string
  expiryDate: string | null
  shelfLife: string | number | null
}

export type StockStatus = 'in-stock' | 'low-stock' | 'out-of-stock'

export interface CabinetSlot {
  id: string
  component?: Component | null
}

export interface CabinetRow {
  id: string
  slots: CabinetSlot[]
}

export interface Cabinet {
  id: string
  name?: string
  status?: string
  temperature: number
  humidity?: number
  maxTemperature?: number
  minHumidity?: number
  maxHumidity?: number
  notes?: string
  lastActivity?: string
  usedSlots?: number
  totalSlots?: number
  rows?: CabinetRow[]
}

export interface SensorReading {
  value: number
  label?: string
  time?: string
  timestamp?: string | number
}

export type AlertLevel = 'critical' | 'warning' | 'info' | string

export interface Alert {
  id: string
  title: string
  message: string
  level: AlertLevel
  time?: string
  timeAgo?: string
  timestamp?: string
  read?: boolean
  cabinetId?: string
  componentId?: string
}