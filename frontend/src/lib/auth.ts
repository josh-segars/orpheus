import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { Session } from '@supabase/supabase-js'

import { supabase } from './supabase'

export type SessionStatus = 'loading' | 'authenticated' | 'unauthenticated'

export interface SessionState {
  session: Session | null
  status: SessionStatus
}

/**
 * useSession — observe the current Supabase auth session.
 *
 * Hydrates synchronously from the persisted session on mount, then subscribes
 * to onAuthStateChange so the hook re-renders on sign-in / sign-out / token
 * refresh. Clearing the React Query cache on sign-out ensures a previously
 * signed-in user's data does not leak into a subsequent session.
 */
export function useSession(): SessionState {
  const [state, setState] = useState<SessionState>({
    session: null,
    status: 'loading',
  })
  const queryClient = useQueryClient()

  useEffect(() => {
    let cancelled = false

    // Initial hydration. supabase.auth.getSession reads from localStorage, so
    // refreshes don't bounce the user back to /login.
    supabase.auth.getSession().then(({ data }) => {
      if (cancelled) return
      setState({
        session: data.session,
        status: data.session ? 'authenticated' : 'unauthenticated',
      })
    })

    const { data } = supabase.auth.onAuthStateChange((event, session) => {
      setState({
        session,
        status: session ? 'authenticated' : 'unauthenticated',
      })
      if (event === 'SIGNED_OUT') {
        queryClient.clear()
      }
    })

    return () => {
      cancelled = true
      data.subscription.unsubscribe()
    }
  }, [queryClient])

  return state
}

/**
 * Kick off the LinkedIn OIDC flow. Returns once the browser has been told
 * to navigate to LinkedIn — no useful return value, the page redirects.
 */
export async function signInWithLinkedIn(redirectTo?: string): Promise<void> {
  const { error } = await supabase.auth.signInWithOAuth({
    provider: 'linkedin_oidc',
    options: redirectTo ? { redirectTo } : undefined,
  })
  if (error) {
    throw error
  }
}

export async function signOut(): Promise<void> {
  const { error } = await supabase.auth.signOut()
  if (error) {
    throw error
  }
}
