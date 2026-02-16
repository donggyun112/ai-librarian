'use client'

import { useState } from 'react'
import Image from 'next/image'
import { createClient } from '@/lib/supabase/client'

export default function LoginPage() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const supabase = createClient()

  const handleGoogleLogin = async () => {
    setLoading(true)
    setError(null)

    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/auth/callback`,
        },
      })

      if (error) {
        setError(error.message)
      }
    } catch (err) {
      setError('로그인 중 오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative flex min-h-screen overflow-hidden bg-black">
      {/* Left side - Login Form */}
      <div className="flex w-full items-center justify-center px-8 lg:w-1/2">
        <div className="w-full max-w-md">
          {/* Header */}
          <div className="mb-10">
            <h1 className="mb-2 text-4xl font-medium text-white">Log into your account</h1>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-6 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3">
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}

          {/* Login Buttons */}
          <div className="space-y-3">
            <button
              onClick={handleGoogleLogin}
              disabled={loading}
              className="flex w-full items-center justify-center gap-3 rounded-full border border-white/20 bg-transparent px-6 py-3.5 text-base font-medium text-white transition-all hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              {loading ? '로그인 중...' : 'Login with Google'}
            </button>
          </div>

          {/* Footer */}
          <div className="mt-8">
            <p className="text-center text-sm text-gray-500">
              By continuing, you agree to AI Librarian's{' '}
              <a href="#" className="text-gray-400 hover:underline">
                Terms of Service
              </a>{' '}
              and{' '}
              <a href="#" className="text-gray-400 hover:underline">
                Privacy Policy
              </a>
            </p>
          </div>
        </div>
      </div>

      {/* Right side - Gradient Background with Libra Symbol */}
      <div className="hidden lg:block lg:w-1/2">
        <div className="relative flex h-full w-full items-center justify-center">
          {/* Gradient Blur Effects */}
          <div className="absolute right-1/4 top-1/4 h-96 w-96 rounded-full bg-blue-500/20 blur-[120px]" />
          <div className="absolute bottom-1/4 right-1/3 h-96 w-96 rounded-full bg-purple-500/20 blur-[120px]" />
          <div className="absolute right-1/2 top-1/2 h-96 w-96 rounded-full bg-cyan-500/10 blur-[100px]" />

          {/* Large Libra Symbol */}
          <div className="relative z-10 opacity-20">
            <Image
              src="/images/logo/libra-logo.svg"
              alt="Libra Symbol"
              width={500}
              height={500}
              className="animate-pulse"
              style={{ animationDuration: '4s' }}
            />
          </div>

          {/* Floating Particles */}
          <div className="absolute inset-0">
            {[
              { left: '10%', top: '15%', size: 8 },
              { left: '80%', top: '10%', size: 12 },
              { left: '85%', top: '40%', size: 8 },
              { left: '15%', top: '50%', size: 10 },
              { left: '90%', top: '70%', size: 8 },
              { left: '10%', top: '80%', size: 12 },
            ].map((particle, i) => (
              <div
                key={i}
                className="absolute rounded-full bg-gradient-to-br from-blue-400 to-purple-400"
                style={{
                  left: particle.left,
                  top: particle.top,
                  width: particle.size,
                  height: particle.size,
                  animation: `pulse ${3 + i * 0.5}s ease-in-out infinite`,
                }}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
