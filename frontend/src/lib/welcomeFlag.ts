/**
 * Tiny localStorage helper for tracking whether the current browser has seen
 * the Welcome screen. The flag exists purely to drive smart routing — once
 * the user clicks "Get Started", subsequent visits skip Welcome and land on
 * Groundwork directly.
 *
 * We intentionally avoid putting this in a Supabase column for now: it's a
 * per-device UX preference, not a piece of durable client state. If a user
 * clears storage or signs in from a new device, they'll see Welcome once
 * more, which is fine.
 *
 * If we ever want this to be cross-device durable, the migration target is
 * `public.clients.welcomed_at timestamptz`, and the read site is the smart
 * index redirect in App.tsx.
 */

const STORAGE_KEY = 'orpheus.welcome.seen'

export function hasSeenWelcome(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    // Private mode / disabled storage — fall back to always showing Welcome.
    return false
  }
}

export function markWelcomeSeen(): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, '1')
  } catch {
    // Same fallback — if we can't write, we just show Welcome again next
    // time, which is the harmless side of the trade-off.
  }
}
