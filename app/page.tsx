'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Cpu, LogIn, UserPlus } from 'lucide-react'

export default function LandingPage() {
  const router = useRouter()
  const [checkingAuth, setCheckingAuth] = useState(true)

  useEffect(() => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null

    if (token) {
      router.replace('/dashboard')
    } else {
      setCheckingAuth(false)
    }
  }, [router])

  // Prevent flash of landing page while checking token
  if (checkingAuth) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0e0720]">
        <div className="size-8 animate-spin rounded-full border-2 border-fuchsia-500 border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0e0720] px-4">
      <div className="flex w-full max-w-sm flex-col items-center text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-violet-950/70 p-3 ring-1 ring-violet-500/30">
          <Cpu className="h-8 w-8 text-fuchsia-400" />
        </div>

        <h1 className="mt-6 text-3xl font-bold tracking-tight text-white">
          Smart Component Storage
        </h1>

        <p className="mt-3 text-sm text-zinc-400">
          Automated telemetry, live shelf-life tracking, and inventory control.
        </p>

        <div className="mt-8 flex w-full flex-col gap-3">
          <Link
            href="/login"
            className="flex w-full items-center justify-center gap-2 rounded-full bg-fuchsia-500 py-3.5 text-sm font-semibold text-white shadow-lg shadow-fuchsia-500/25 transition hover:bg-fuchsia-400"
          >
            <LogIn className="h-4 w-4" />
            Sign In to Account
          </Link>

          <Link
            href="/register"
            className="flex w-full items-center justify-center gap-2 rounded-full border border-violet-800/60 bg-violet-950/30 py-3.5 text-sm font-semibold text-violet-200 transition hover:bg-violet-900/40"
          >
            <UserPlus className="h-4 w-4 text-fuchsia-400" />
            Create New Account
          </Link>
        </div>
      </div>
    </div>
  )
}