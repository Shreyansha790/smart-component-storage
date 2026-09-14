'use client'

import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { RefreshCw } from 'lucide-react'
import { cabinets as initialCabinets } from '@/data/mock-data'
import { fetchApi } from '@/lib/api'
import { cn } from '@/lib/utils'
import { ScreenHeader } from '@/components/app-shell'
import { CabinetSlotGrid, SlotComponent } from '@/components/cabinet-slot-grid'

function CabinetsView() {
  const params = useSearchParams()
  const cabParam = params.get('cab')

  const [cabinetList, setCabinetList] = useState<any[]>(initialCabinets)
  const [index, setIndex] = useState(0)
  const [loading, setLoading] = useState(false)

  const loadCabinets = async () => {
    setLoading(true)
    try {
      const inventoryData = await fetchApi<any[]>('/inventory')

      if (Array.isArray(inventoryData) && inventoryData.length > 0) {
        const normalizeCabinetId = (rawLoc: string) => {
          const loc = (rawLoc || '').toUpperCase()
          if (loc.includes('CAB-B') || loc.startsWith('B') || loc.includes('B -')) {
            return 'CAB-B'
          }
          return 'CAB-A'
        }

        const canonicalCabinets = ['CAB-A', 'CAB-B']

        const builtCabinets = canonicalCabinets.map((cabId) => {
          const matchingItems = inventoryData.filter(
            (item) => normalizeCabinetId(item.cabinet_location) === cabId
          )

          const assignedItemIds = new Set<string>()

          const rows = ['A', 'B'].map((rowLetter, rowIndex) => {
            const shelfNum = rowIndex + 1 // Row A = Shelf 1, Row B = Shelf 2

            const slots = [1, 2, 3, 4].map((slotNum) => {
              const slotKey = `${rowLetter}${slotNum}` // e.g. "A1", "B4"

              // Explicit slot match using resilient string & regex patterns
              const itemInSlot = matchingItems.find((item) => {
                const itemId = String(item.id ?? item.batch_id)
                if (assignedItemIds.has(itemId)) return false

                const loc = (item.cabinet_location || '').toUpperCase().trim()

                // 1. Row match: "ROW-B", "ROW B", "SHELF 2", "SHELF B"
                const hasRow =
                  loc.includes(`ROW-${rowLetter}`) ||
                  loc.includes(`ROW ${rowLetter}`) ||
                  loc.includes(`SHELF ${shelfNum}`) ||
                  loc.includes(`SHELF ${rowLetter}`)

                // 2. Slot match: "SLOT 4", "SLOT-4", "B4", or ends with the digit
                const hasSlot =
                  loc.includes(`SLOT ${slotNum}`) ||
                  loc.includes(`SLOT-${slotNum}`) ||
                  loc.includes(`SLOT ${rowLetter}${slotNum}`) ||
                  loc.includes(`ROW-${rowLetter}${slotNum}`) ||
                  new RegExp(`\\b${slotNum}\\b`).test(loc.split('SLOT')[1] || '')

                return hasRow && hasSlot
              })

              if (itemInSlot) {
                assignedItemIds.add(String(itemInSlot.id ?? itemInSlot.batch_id))
              }

              return {
                id: `ROW-${slotKey}`,
                occupied: Boolean(itemInSlot),
                component: itemInSlot
                  ? {
                      id: String(itemInSlot.id || itemInSlot.batch_id),
                      name: itemInSlot.part_number || itemInSlot.name || 'Component',
                      partNumber: itemInSlot.part_number || itemInSlot.name || '',
                      quantity: itemInSlot.quantity ?? 1,
                      batch: itemInSlot.batch_id || 'N/A',
                      category: itemInSlot.category || 'Other',
                    }
                  : null,
              }
            })

            return {
              id: `ROW-${rowLetter}`,
              label: `Row ${rowLetter}`,
              slots,
            }
          })

          const totalSlots = 8
          const occupiedCount = matchingItems.length
          const utilizationRate = Math.min(100, Math.round((occupiedCount / totalSlots) * 100))

          return {
            id: cabId,
            name: `Smart Cabinet ${cabId.replace('CAB-', '')}`,
            status: 'online',
            temperature: 24.2,
            humidity: 45,
            utilization: utilizationRate,
            componentCount: occupiedCount,
            rows,
          }
        })

        setCabinetList(builtCabinets)
      } else {
        setCabinetList(initialCabinets)
      }
    } catch {
      setCabinetList(initialCabinets)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCabinets()
  }, [])

  useEffect(() => {
    if (cabParam && cabinetList.length > 0) {
      const cleanCab = cabParam.toUpperCase().includes('B') ? 'CAB-B' : 'CAB-A'
      const foundIdx = cabinetList.findIndex((c) => c.id === cleanCab)
      if (foundIdx !== -1) {
        setIndex(foundIdx)
      }
    }
  }, [cabParam, cabinetList])

  const cabinet = cabinetList[index] || initialCabinets[0]

  const metrics = [
    { label: 'Temp', value: `${cabinet?.temperature ?? 24}°C`, tone: 'text-blue' },
    { label: 'Humidity', value: `${cabinet?.humidity ?? 45}%`, tone: 'text-purple' },
    { label: 'Utilization', value: `${cabinet?.utilization ?? 0}%`, tone: 'text-lime' },
  ]

  const handleAddComponent = async (slotId: string, newComponent: SlotComponent) => {
    const cleanSlotId = slotId.replace(/^ROW-/, '').trim()
    const rowChar = cleanSlotId.charAt(0) || 'A'
    const slotNumber = cleanSlotId.slice(1) || '1'

    try {
      await fetchApi('/inventory', {
        method: 'POST',
        body: JSON.stringify({
          batch_id: newComponent.batch || `BATCH-${Date.now().toString().slice(-4)}`,
          part_number: newComponent.name,
          manufacturer: 'Generic',
          category: 'Other',
          cabinet_location: `${cabinet.id} - ROW-${rowChar} - SLOT ${slotNumber}`,
          quantity: Number(newComponent.quantity) || 1,
          stored_date: new Date().toISOString().split('T')[0],
          shelf_life_days: 365,
        }),
      })
      await loadCabinets()
    } catch {
      await loadCabinets()
    }
  }

  return (
    <div className="pb-6">
      <ScreenHeader
        title="Smart Cabinets"
        action={
          <button
            type="button"
            onClick={loadCabinets}
            disabled={loading}
            className="flex size-10 items-center justify-center rounded-xl border border-white/10 bg-card text-muted-foreground transition active:scale-95 disabled:opacity-50"
            title="Refresh cabinets"
          >
            <RefreshCw className={cn('size-4', loading && 'animate-spin text-lime')} />
          </button>
        }
      />

      <div className="flex gap-2 px-5">
        {cabinetList.map((c, i) => (
          <button
            key={c.id}
            type="button"
            onClick={() => setIndex(i)}
            className={cn(
              'flex-1 rounded-xl border py-2.5 text-sm font-medium transition-colors',
              i === index
                ? 'border-lime/40 bg-lime/15 text-lime'
                : 'border-white/10 bg-card text-muted-foreground'
            )}
          >
            {c.id}
          </button>
        ))}
      </div>

      <section className="mt-4 px-5">
        <div className="rounded-2xl border border-white/8 bg-card p-4">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-lg font-bold">{cabinet?.name ?? 'Cabinet'}</h2>
              <p className="text-xs text-muted-foreground">
                {cabinet?.id} · {cabinet?.componentCount ?? 0} components
              </p>
            </div>
            <span
              className={cn(
                'flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium',
                cabinet?.status === 'online'
                  ? 'border-lime/30 bg-lime/10 text-lime'
                  : 'border-white/10 text-muted-foreground'
              )}
            >
              <span className="size-1.5 rounded-full bg-current" />
              {cabinet?.status === 'online' ? 'Online' : 'Offline'}
            </span>
          </div>

          <div className="mt-4 grid grid-cols-3 gap-2">
            {metrics.map((m) => (
              <div key={m.label} className="rounded-xl bg-white/[0.03] p-2 text-center">
                <p className="text-[11px] text-muted-foreground">{m.label}</p>
                <p className={cn('mt-1 text-lg font-bold', m.tone)}>{m.value}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-5 px-5">
        <CabinetSlotGrid
          cabinet={cabinet}
          onAddComponent={handleAddComponent}
        />
      </section>
    </div>
  )
}

export default function CabinetsPage() {
  return (
    <Suspense fallback={<div className="px-5 py-10 text-sm text-muted-foreground">Loading…</div>}>
      <CabinetsView />
    </Suspense>
  )
}