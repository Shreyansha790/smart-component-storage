'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Settings, LogOut } from 'lucide-react'
import { systemInfo } from '@/data/mock-data'
import { ScreenHeader } from '@/components/app-shell'
import { ToggleSwitch } from '@/components/toggle-switch'

interface UserData {
  full_name?: string
  email: string
  role?: string
}

export default function ProfilePage() {
  const router = useRouter()
  const [currentUser, setCurrentUser] = useState<UserData | null>(null)
  const [loading, setLoading] = useState(true)

  const [prefs, setPrefs] = useState({
    push: true,
    dark: true,
    autoSync: true,
  })

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      setLoading(false)
      return
    }

    fetch('http://localhost:8000/auth/me', {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then((res) => {
        if (!res.ok) throw new Error('Unauthorized')
        return res.json()
      })
      .then((data) => setCurrentUser(data))
      .catch(() => {
        localStorage.removeItem('token')
        setCurrentUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  const handleSignOut = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    router.push('/login')
  }

  const displayName = currentUser?.full_name || 'User'
  const displayEmail = currentUser?.email || 'Not logged in'
  const displayRole = currentUser?.role || 'Guest'
  const initials = displayName
    .split(' ')
    .filter(Boolean)
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || 'U'

  const stats = [
    { label: 'Components', value: 24 },
    { label: 'Cabinets', value: 3 },
    { label: 'Alerts Set', value: 5 },
  ]

  const preferences = [
    {
      key: 'push' as const,
      title: 'Push Notifications',
      desc: 'Stock alerts, sensor warnings',
    },
    { key: 'dark' as const, title: 'Dark Mode', desc: 'Always on for this interface' },
    { key: 'autoSync' as const, title: 'Auto-Sync Cabinets', desc: 'Every 60 seconds' },
  ]

  const system = [
    { label: 'Version', value: systemInfo.version },
    { label: 'Status', value: systemInfo.status },
    { label: 'Active Nodes', value: systemInfo.activeNodes },
    { label: 'Last Backup', value: systemInfo.lastBackup },
    { label: 'Database', value: systemInfo.databaseStatus },
    { label: 'Uptime', value: systemInfo.uptime },
    { label: 'Environment', value: systemInfo.environment },
  ]
  return (
    <div className="pb-6">
      <ScreenHeader
        title="Profile"
        action={
          <Link
            href="/settings"
            className="flex size-10 items-center justify-center rounded-xl border border-white/10 bg-card"
            aria-label="Open settings"
          >
            <Settings className="size-5" />
          </Link>
        }
      />

      <section className="px-5">
        <div className="rounded-2xl border border-white/8 bg-card p-4">
          <div className="flex items-center gap-4">
            <div className="flex size-14 items-center justify-center rounded-2xl bg-gradient-to-br from-purple to-blue text-lg font-bold text-white">
              {initials}
            </div>
            <div>
              <h2 className="text-lg font-bold">{loading ? 'Loading...' : displayName}</h2>
              <p className="text-sm text-blue">{loading ? '...' : displayEmail}</p>
              <span className="mt-1 inline-flex rounded-full border border-lime/30 bg-lime/10 px-2 py-0.5 text-[10px] font-medium uppercase text-lime">
                {loading ? '...' : displayRole}
              </span>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-3 gap-2 border-t border-white/8 pt-4">
            {stats.map((s) => (
              <div key={s.label} className="text-center">
                <p className="text-xl font-bold tabular-nums">{s.value}</p>
                <p className="text-[11px] text-muted-foreground">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-4 px-5">
        <div className="rounded-2xl border border-white/8 bg-card p-1">
          <p className="px-3 pt-3 pb-1 text-[11px] font-semibold tracking-widest text-blue">
            PREFERENCES
          </p>
          {preferences.map((p, i) => (
            <div
              key={p.key}
              className={`flex items-center justify-between px-3 py-3 ${
                i > 0 ? 'border-t border-white/8' : ''
              }`}
            >
              <div>
                <p className="text-sm font-medium">{p.title}</p>
                <p className="text-xs text-muted-foreground">{p.desc}</p>
              </div>
              <ToggleSwitch
                label={p.title}
                checked={prefs[p.key]}
                onChange={(v) => setPrefs((prev) => ({ ...prev, [p.key]: v }))}
              />
            </div>
          ))}
        </div>
      </section>

      <section className="mt-4 px-5">
        <div className="rounded-2xl border border-white/8 bg-card p-1">
          <p className="px-3 pt-3 pb-1 text-[11px] font-semibold tracking-widest text-muted-foreground">
            SYSTEM
          </p>
          {system.map((s, i) => (
            <div
              key={s.label}
              className={`flex items-center justify-between px-3 py-3 ${
                i > 0 ? 'border-t border-white/8' : ''
              }`}
            >
              <span className="text-sm text-muted-foreground">{s.label}</span>
              <span className="font-mono text-sm">{s.value}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-4 px-5">
        <button
          type="button"
          onClick={handleSignOut}
          className="flex w-full items-center justify-center gap-2 rounded-2xl border border-danger/30 bg-danger/10 py-3.5 text-sm font-semibold text-danger transition-opacity hover:opacity-80"
        >
          <LogOut className="size-4" /> Sign Out
        </button>
      </section>
    </div>
  )
}