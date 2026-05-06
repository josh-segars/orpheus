import { createClient } from '@supabase/supabase-js'

/**
 * Shared Supabase browser client. One instance per app — the auth state is
 * held inside the client and observed via supabase.auth.onAuthStateChange in
 * src/lib/auth.ts.
 *
 * Configured to:
 *   - persist sessions in localStorage (default)
 *   - auto-refresh access tokens before they expire
 *   - detect the OAuth callback hash on page load and exchange it for a session
 *
 * VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY are read at module-eval time and
 * the app refuses to boot if either is missing — fail fast beats a confusing
 * 401 cascade later.
 */

const url = import.meta.env.VITE_SUPABASE_URL
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!url || !anonKey) {
  throw new Error(
    'Missing Supabase configuration. Set VITE_SUPABASE_URL and ' +
      'VITE_SUPABASE_ANON_KEY in frontend/.env.local. See ' +
      'frontend/.env.local.example for the full list.',
  )
}

export const supabase = createClient(url, anonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
})
