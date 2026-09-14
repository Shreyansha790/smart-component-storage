'use client'

import Link from 'next/link'
import { Cpu, LogIn, UserPlus, ShieldCheck } from 'lucide-react'

export default function WelcomePage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-12">
      {/* Glow highlight background */}
      <div className="absolute inset-0 -z-10 flex items-center justify-center">
        <div className="size-96 rounded-full bg-lime/10 blur-3xl" />
      </div>

      <div className="w-full max-w-md space-y-8 text-center">
        {/* Logo / Badge */}
        <div className="mx-auto flex size-20 items-center justify-center rounded-2xl border border-white/10 bg-card/80 shadow-2xl shadow-lime/5">
          <Cpu className="size-10 text-lime" />
        </div>

        {/* Header */}
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight text-white">
            Smart Component Storage
          </h1>
          <p className="text-sm text-muted-foreground">
            Automated telemetry, live shelf-life tracking, and inventory control.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col gap-3.5 pt-4">
          <Link
            href="/login"
            className="flex items-center justify-center gap-2 rounded-xl bg-lime py-3.5 text-sm font-semibold text-black shadow-lg shadow-lime/20 transition active:scale-[0.98] hover:bg-lime/90"
          >
            <LogIn className="size-4" />
            Sign In to Account
          </Link>

          <Link
            href="/register"
            className="flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-card/60 py-3.5 text-sm font-semibold text-white transition active:scale-[0.98] hover:bg-card hover:border-white/20"
          >
            <UserPlus className="size-4 text-lime" />
            Create New Account
          </Link>
        </div>

        {/* Trust pill */}
        <div className="pt-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-white/5 bg-white/[0.03] px-3.5 py-1.5 text-xs text-muted-foreground">
            <ShieldCheck className="size-3.5 text-lime" />
            Multi-Admin Protected System
          </div>
        </div>
      </div>
    </div>
  )
}