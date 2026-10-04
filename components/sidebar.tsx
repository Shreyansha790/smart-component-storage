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
    <aside className="hidden md:flex min-h-screen w-64 shrink-0 flex-col border-r border-violet-900/30 bg-[#0d041c]/90 p-4 backdrop-blur-2xl">
      {/* Brand */}
      <div className="mb-6 flex items-center gap-3 px-3 py-2">
        <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-fuchsia-500 to-violet-600 shadow-[0_0_15px_rgba(217,70,239,0.5)]">
          <Cpu className="size-5 text-white" />
        </div>
        <div>
          <h1 className="font-mono text-base font-bold tracking-tight text-white">
            SMART STORAGE
          </h1>
          <p className="font-mono text-[10px] text-fuchsia-400">
            CYBER HUD v2.4
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
                  ? 'border border-fuchsia-500/40 bg-gradient-to-r from-fuchsia-600/30 to-violet-600/20 text-white shadow-[0_0_15px_rgba(217,70,239,0.25)]'
                  : 'text-purple-300/70 hover:bg-violet-950/40 hover:text-white'
              }`}
            >
              <Icon className="size-4 shrink-0 text-fuchsia-400" />
              <span>{item.name}</span>
            </Link>
          )
        })}
      </nav>

      {/* Bottom Navigation */}
      <div className="flex flex-col gap-1.5 border-t border-violet-900/40 pt-4 font-mono text-xs">
        {bottomNavigation.map((item) => {
          const Icon = item.icon
          const active = pathname === item.href

          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 rounded-xl px-3.5 py-2.5 transition ${
                active
                  ? 'border border-fuchsia-500/40 bg-violet-600/30 text-white'
                  : 'text-purple-300/70 hover:bg-violet-950/40 hover:text-white'
              }`}
            >
              <Icon className="size-4 shrink-0 text-purple-400" />
              <span>{item.name}</span>
            </Link>
          )
        })}
      </div>
    </aside>
  )
}