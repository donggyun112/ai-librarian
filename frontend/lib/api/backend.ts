import { createClient } from '@/lib/supabase/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'

/**
 * 서버사이드 인증 fetch 유틸리티
 *
 * Supabase 세션에서 JWT 토큰을 추출하여
 * 백엔드 API 호출 시 Authorization 헤더에 포함합니다.
 *
 * 401 응답 시 그대로 반환하여 호출자가 처리하도록 합니다.
 */
export async function backendFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const supabase = await createClient()
  const {
    data: { session },
  } = await supabase.auth.getSession()

  const headers = new Headers(options.headers)

  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  if (session?.access_token) {
    headers.set('Authorization', `Bearer ${session.access_token}`)
  }

  return fetch(`${BACKEND_URL}${path}`, {
    ...options,
    headers,
  })
}
