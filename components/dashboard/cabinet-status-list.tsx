import type { Cabinet } from '@/types'
import { cn } from '@/lib/utils'

export function CabinetStatusList({ cabinets }: { cabinets: Cabinet[] }) {
  return (
    <ul className="flex flex-col gap-4">
      {cabinets.map((cab) => {
        const used = cab.usedSlots ?? cab.rows?.reduce((acc, r) => acc + r.slots.filter((s) => Boolean(s.component)).length, 0) ?? 0
        const total = cab.totalSlots ?? cab.rows?.reduce((acc, r) => acc + r.slots.length, 0) ?? 8
        const pct = total > 0 ? Math.round((used / total) * 100) : 0
        const hot = cab.temperature >= 26
        return (
          <li key={cab.id} className="flex flex-col gap-1.5">
            <div className="flex items-center gap-2 text-xs">
              <span
                className={cn(
                  'size-2 rounded-full',
                  hot ? 'bg-warning' : 'bg-lime',
                )}
              />
              <span className="font-medium">{cab.id}</span>
              <span className="ml-auto font-mono text-muted-foreground">
                {used}/{total}
              </span>
              <span
                className={cn(
                  'w-12 text-right font-mono',
                  hot ? 'text-warning' : 'text-blue',
                )}
              >
                {cab.temperature}°
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-white/8">
              <div
                className={cn('h-full rounded-full', hot ? 'bg-warning' : 'bg-lime')}
                style={{ width: `${pct}%` }}
              />
            </div>
          </li>
        )
      })}
    </ul>
  )
}
