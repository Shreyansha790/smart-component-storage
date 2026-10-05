'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  Package,
  Archive,
  Thermometer,
  CalendarClock,
  Bell,
  User,
  Settings,
  Cpu,
} from 'lucide-react'

const navigation = [
  {
    name: 'Dashboard',
    href: '/dashboard',
    icon: LayoutDashboard,
  },
  {
    name: 'Inventory',
    href: '/inventory',
    icon: Package,
  },
  {
    name: 'Cabinets',
    href: '/cabinets',
    icon: Archive,
  },
  {
    name: 'Environment',
    href: '/environment',
    icon: Thermometer,
  },
  {
    name: 'Expiry',
    href: '/expiry',
    icon: CalendarClock,
  },
  {
    name: 'Alerts',
    href: '/alerts',
    icon: Bell,
  },
]

const bottomNavigation = [
  {
    name: 'Profile',
    href: '/profile',
    icon: User,
  },
  {
    name: 'Settings',
    href: '/settings',
    icon: Settings,
  },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="hidden md:flex min-h-screen w-64 shrink-0 flex-col border-r border-slate-200/80 bg-white/90 p-4 backdrop-blur-2xl">
      {/* Brand */}
      <div className="mb-6 flex items-center gap-3 px-3 py-2">
        <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500 to-indigo-600 shadow-md shadow-sky-500/20 text-white">
          <Cpu className="size-5" />
        </div>
        <div>
          <h1 className="font-mono text-base font-bold tracking-tight text-slate-900">
            SMART STORAGE
          </h1>
          <p className="font-mono text-[10px] text-sky-600 font-semibold">
            LABORATORY v3.0
          </p>
        </div>
      </div>

      {/* Main Navigation */}
      <nav className="flex flex-1 flex-col gap-1.5 font-mono text-xs">
        {navigation.map((item) => {
          const Icon = item.icon
          const active =
            pathname === item.href ||
            (item.name === 'Dashboard' && (pathname === '/' || pathname === '/dashboard'))

          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 rounded-xl px-3.5 py-2.5 transition ${
                active
                  ? 'border border-sky-200 bg-sky-50 font-bold text-sky-700 shadow-sm'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              <Icon className={`size-4 shrink-0 ${active ? 'text-sky-600' : 'text-slate-400'}`} />
              <span>{item.name}</span>
            </Link>
          )
        })}
      </nav>

      {/* Bottom Navigation */}
      <div className="flex flex-col gap-1.5 border-t border-slate-200/80 pt-4 font-mono text-xs">
        {bottomNavigation.map((item) => {
          const Icon = item.icon
          const active = pathname === item.href

          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 rounded-xl px-3.5 py-2.5 transition ${
                active
                  ? 'border border-sky-200 bg-sky-50 font-bold text-sky-700 shadow-sm'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              <Icon className={`size-4 shrink-0 ${active ? 'text-sky-600' : 'text-slate-400'}`} />
              <span>{item.name}</span>
            </Link>
          )
        })}
      </div>
    </aside>
  )
}