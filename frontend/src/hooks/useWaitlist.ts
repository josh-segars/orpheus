import { useMutation } from '@tanstack/react-query'

import { supabase } from '../lib/supabase'

/**
 * Join-the-waitlist mutation for the www marketing landing page (ORPHEUS-8).
 *
 * Writes directly to public.waitlist through the browser anon client — the
 * migration-017 RLS policy allows anon INSERT only (no read-back). There is
 * deliberately no backend endpoint: the marketing site is served by this same
 * frontend (hostname-routed) and the anon key is already configured.
 *
 * A duplicate email trips the unique index on lower(email) and comes back as
 * Postgres error 23505; we swallow it and report success, since "you're
 * already on the list" is the same outcome to the visitor.
 */
export interface JoinWaitlistInput {
  firstName: string
  lastName: string
  email: string
  /** Offerings selected: 'beta_access' and/or 'live_workshop'. */
  interests: string[]
}

export function useJoinWaitlist() {
  return useMutation<{ email: string }, Error, JoinWaitlistInput>({
    mutationFn: async ({ firstName, lastName, email, interests }) => {
      const clean = email.trim().toLowerCase()

      const { error } = await supabase.from('waitlist').insert({
        email: clean,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        interests,
        source: 'www-landing',
        user_agent:
          typeof navigator !== 'undefined' ? navigator.userAgent : null,
      })

      // 23505 = unique_violation → already on the list. Treat as success.
      if (error && error.code !== '23505') {
        throw new Error(error.message)
      }

      return { email: clean }
    },
  })
}
