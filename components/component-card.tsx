import Link from 'next/link'
import { Calendar } from 'lucide-react'
import type { Component } from '@/types'
import { getStockStatus } from '@/lib/inventory'
import { cn } from '@/lib/utils'
import { CategoryIcon } from '@/components/category-icon'
import { StatusBadge } from '@/components/status-badge'

const qtyColor = {
  'in-stock': 'text-foreground',
  'low-stock': 'text-warning',
  'out-of-stock': 'text-danger',
} as const

function getExpiryBadge(expiryDateStr?: string | null) {
  if (!expiryDateStr) return null

  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const expiry = new Date(expiryDateStr)
  expiry.setHours(0, 0, 0, 0)

  const diffTime = expiry.getTime() - today.getTime()
  const daysLeft = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

  if (daysLeft < 0) {
    return {
      label: `Expired (${Math.abs(daysLeft)}d ago)`,
      className: 'border-rose-500/30 bg-rose-500/15 text-rose-400',
    }
  }
  if (daysLeft <= 7) {
    return {
      label: `${daysLeft}d left`,
      className: 'border-amber-500/30 bg-amber-500/15 text-amber-300 font-semibold',
    }
  }
  return {
    label: `${daysLeft}d left`,
    className: 'border-white/10 bg-white/5 text-muted-foreground',
  }
}

export function ComponentCard({ component }: { component: Component }) {
  const status = getStockStatus(component)
  const expiryBadge = getExpiryBadge(component.expiryDate)

  return (
    <Link
      href={`/inventory/${component.id}`}
      className={cn(
        'flex items-center gap-3 rounded-2xl border p-3 transition-colors',
        status === 'out-of-stock'
          ? 'border-danger/30 bg-danger/[0.06]'
          : 'border-white/8 bg-card hover:border-white/15',
      )}
    >
      <CategoryIcon category={component.category} />

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">{component.name}</p>
        <p className="truncate text-xs text-muted-foreground">{component.category}</p>

        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
          <span className="rounded-md bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            {component.cabinet}/{component.slot}
          </span>

          {component.expiryDate && (
            <span
              className={cn(
                'flex items-center gap-1 rounded-md border px-1.5 py-0.5 font-mono text-[10px]',
                expiryBadge?.className
              )}
              title={`Expires: ${component.expiryDate}`}
            >
              <Calendar className="size-2.5" />
              <span>Exp: {component.expiryDate}</span>
              {expiryBadge && <span>({expiryBadge.label})</span>}
            </span>
          )}
        </div>
      </div>

      <div className="flex flex-col items-end gap-1.5">
        <span className={cn('text-xl font-bold tabular-nums', qtyColor[status])}>
          {component.quantity}
        </span>
        <StatusBadge status={status} />
      </div>
    </Link>
  )
}