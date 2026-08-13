/**
 * In-app browser detection (ORPHEUS-130).
 *
 * The problem this exists to solve is specific and was invisible from
 * inside the product for weeks. A tester taps a sign-in link from a
 * LinkedIn DM. The link opens in LinkedIn's *in-app browser* — a webview
 * hosted by the LinkedIn app, not Safari or Chrome. We hand off to
 * `linkedin.com/oauth/v2/authorization`, and the LinkedIn app
 * deep-link-intercepts its own domain: instead of rendering the OAuth
 * consent screen, it swallows the navigation and drops the user on their
 * feed. They never come back. From our side the trail simply ends —
 * Supabase logs the `/authorize` redirect and no `/callback` ever
 * arrives, so no auth.users row is created and not one line of our own
 * code runs.
 *
 * The live case: four attempts, four `/authorize` hits, zero
 * `/callback` hits, no user row (2026-08-13). Read as a "login loop" in
 * the report, but nothing was looping — the flow died at the provider.
 *
 * Every in-app browser in the set below breaks OAuth in some comparable
 * way (cookie partitioning, blocked cross-origin redirects, no
 * window.open). LinkedIn's is the worst case only because the identity
 * provider and the host app are the same company, so the interception is
 * guaranteed rather than incidental.
 *
 * DETECTION IS A HEURISTIC, AND THAT SHAPES THE UI. User-agent sniffing
 * is unreliable by construction: vendors change tokens without notice,
 * and a webview can be made to look like anything. So the guard this
 * feeds is a hard block *with an escape hatch* — see `setOverride`. A
 * false positive costs a user one extra tap; a false negative just
 * returns them to today's behaviour.
 */

/** An in-app browser we recognise, and the host OS if we can tell. */
export interface InAppBrowserInfo {
  /** Display name for the host app, e.g. "LinkedIn". */
  name: string
  /** Drives which "open in browser" gesture we describe. */
  platform: 'ios' | 'android' | 'unknown'
}

/**
 * Ordered most-specific first. Facebook's family shares the `FBAN` /
 * `FBAV` tokens across Facebook and Messenger, so Messenger is tested
 * ahead of the generic Facebook match.
 *
 * Deliberately NOT exhaustive — WeChat, Line, Snapchat, TikTok, Pinterest
 * and the Google app all have the same failure mode and can be appended
 * here as they turn up in real reports. The set below is the one our
 * invitations actually travel through today [Josh, 2026-08-13].
 *
 * Every pattern is checked against real browser UAs in the test suite:
 * Chrome/Safari on iOS carry `CriOS` / `Version`, Firefox carries
 * `FxiOS`, and none of them contain these tokens. The one to keep an eye
 * on is the generic Android WebView marker `; wv` — Chrome for Android
 * does not emit it, but a browser built on the system WebView could.
 */
const IN_APP_PATTERNS: ReadonlyArray<{ name: string; pattern: RegExp }> = [
  { name: 'LinkedIn', pattern: /LinkedInApp|com\.linkedin\.android/i },
  { name: 'Instagram', pattern: /Instagram/i },
  { name: 'Messenger', pattern: /FBAN\/Messenger|MessengerLite/i },
  { name: 'Facebook', pattern: /FBAN|FBAV|FB_IAB/i },
  { name: 'Slack', pattern: /Slack(?:_SSB)?\//i },
  { name: 'X', pattern: /Twitter(?:Android)?|Twitter for i(?:Phone|Pad)/i },
  { name: 'your app', pattern: /;\s*wv\)/i },
]

function resolvePlatform(ua: string): InAppBrowserInfo['platform'] {
  if (/iPhone|iPad|iPod/i.test(ua)) return 'ios'
  if (/Android/i.test(ua)) return 'android'
  return 'unknown'
}

/**
 * Identify the in-app browser hosting this page, or null for a real one.
 *
 * `ua` is injectable so the tests can drive it without touching a
 * read-only global; it defaults to the live navigator.
 */
export function detectInAppBrowser(
  ua: string = typeof navigator === 'undefined' ? '' : navigator.userAgent,
): InAppBrowserInfo | null {
  if (!ua) return null

  for (const { name, pattern } of IN_APP_PATTERNS) {
    if (pattern.test(ua)) {
      return { name, platform: resolvePlatform(ua) }
    }
  }
  return null
}

const OVERRIDE_KEY = 'orpheus.inAppBrowserOverride'

/**
 * Module-level mirror of the override.
 *
 * sessionStorage is the primary store so the choice survives the
 * navigations within a sign-in attempt, but it is exactly the thing
 * these environments are unreliable about (ORPHEUS-92 learned this the
 * hard way with the invitation token). The in-memory copy guarantees the
 * escape hatch works for as long as the document lives even when storage
 * throws or is silently partitioned away.
 */
let overrideInMemory = false

/** Has the user chosen to proceed despite the warning? */
export function isOverridden(): boolean {
  if (overrideInMemory) return true
  try {
    return sessionStorage.getItem(OVERRIDE_KEY) === '1'
  } catch {
    return false
  }
}

/** Record the "try anyway" choice for the rest of this session. */
export function setOverride(): void {
  overrideInMemory = true
  try {
    sessionStorage.setItem(OVERRIDE_KEY, '1')
  } catch {
    // In-memory copy above already covers this document.
  }
}

/** Test seam — clears both stores. Not called by application code. */
export function clearOverride(): void {
  overrideInMemory = false
  try {
    sessionStorage.removeItem(OVERRIDE_KEY)
  } catch {
    // Nothing useful to do.
  }
}

/**
 * Should the calling page replace its sign-in action with the guard?
 *
 * Returns the detected host app when the page should be blocked, or null
 * when it should render normally (a real browser, or a user who has
 * taken the escape hatch).
 *
 * Not a hook — it reads no React state and pages call it during render,
 * which keeps the three call sites to a single line each.
 */
export function shouldBlockOAuth(
  ua?: string,
): InAppBrowserInfo | null {
  if (isOverridden()) return null
  return detectInAppBrowser(ua)
}
