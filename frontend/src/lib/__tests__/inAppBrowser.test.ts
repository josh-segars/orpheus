/**
 * In-app browser detection — ORPHEUS-130.
 *
 * The load-bearing half of this suite is the negative half. A false
 * positive hard-blocks a real browser, so every mainstream mobile and
 * desktop UA is pinned as "not an in-app browser"; if a future pattern
 * is written loosely enough to catch Safari or Chrome, these fail before
 * anyone ships it.
 */
import { afterEach, describe, expect, it } from 'vitest'

import {
  clearOverride,
  detectInAppBrowser,
  isOverridden,
  setOverride,
  shouldBlockOAuth,
} from '../inAppBrowser'

// ── Real browsers (must never match) ───────────────────────────────────

const REAL_BROWSERS: Record<string, string> = {
  'iOS Safari':
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
  'iOS Chrome':
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/123.0.6312.52 Mobile/15E148 Safari/604.1',
  'iOS Firefox':
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/124.0 Mobile/15E148 Safari/605.1.15',
  'Android Chrome':
    'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36',
  'Android Firefox':
    'Mozilla/5.0 (Android 14; Mobile; rv:124.0) Gecko/124.0 Firefox/124.0',
  'macOS Safari':
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
  'macOS Chrome':
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
  'Windows Edge':
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.2420.65',
}

// ── In-app browsers (must match, with the right host name) ─────────────

const IN_APP: Array<[string, string, string]> = [
  [
    'LinkedIn iOS',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 [LinkedInApp]',
    'LinkedIn',
  ],
  [
    'LinkedIn Android',
    'Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/UQ1A.240105.004; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/123.0.0.0 Mobile Safari/537.36 [LinkedInApp]',
    'LinkedIn',
  ],
  [
    'Instagram Android',
    'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36 Instagram 302.0.0.23.113 Android',
    'Instagram',
  ],
  [
    'Facebook iOS',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 [FBAN/FBIOS;FBAV/456.0.0.36.108;FBBV/12345]',
    'Facebook',
  ],
  [
    'Messenger iOS',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 [FBAN/Messenger;FBAV/456.0.0.36.108]',
    'Messenger',
  ],
  [
    'Slack iOS',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Slack/23.11.0',
    'Slack',
  ],
  [
    'X iOS',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Twitter for iPhone',
    'X',
  ],
  [
    'X Android',
    'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36 TwitterAndroid',
    'X',
  ],
  [
    'generic Android WebView',
    'Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/UQ1A.240105.004; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/123.0.0.0 Mobile Safari/537.36',
    'your app',
  ],
]

afterEach(() => {
  clearOverride()
})

describe('detectInAppBrowser', () => {
  it.each(Object.entries(REAL_BROWSERS))(
    'does not flag %s',
    (_label, ua) => {
      expect(detectInAppBrowser(ua)).toBeNull()
    },
  )

  it.each(IN_APP)('flags %s as %s', (_label, ua, expected) => {
    expect(detectInAppBrowser(ua)?.name).toBe(expected)
  })

  it('resolves the host platform so the guard can name the gesture', () => {
    expect(detectInAppBrowser(IN_APP[0][1])?.platform).toBe('ios')
    expect(detectInAppBrowser(IN_APP[1][1])?.platform).toBe('android')
  })

  it('prefers Messenger over the generic Facebook family match', () => {
    // Both carry FBAN/FBAV; order in the pattern list is what separates
    // them, and getting it backwards would name the wrong app on screen.
    expect(detectInAppBrowser(IN_APP[4][1])?.name).toBe('Messenger')
  })

  it('returns null for an empty user agent', () => {
    expect(detectInAppBrowser('')).toBeNull()
  })
})

describe('the escape hatch', () => {
  it('stops blocking once the override is set', () => {
    const linkedIn = IN_APP[0][1]
    expect(shouldBlockOAuth(linkedIn)).not.toBeNull()

    setOverride()

    expect(isOverridden()).toBe(true)
    expect(shouldBlockOAuth(linkedIn)).toBeNull()
  })

  it('survives sessionStorage being unavailable', () => {
    // The webviews this targets are exactly the environments that
    // partition or throw on storage (the ORPHEUS-92 lesson), so the
    // in-memory mirror has to carry the override on its own.
    const original = Object.getOwnPropertyDescriptor(
      window,
      'sessionStorage',
    )
    Object.defineProperty(window, 'sessionStorage', {
      configurable: true,
      get() {
        throw new Error('storage disabled')
      },
    })

    try {
      setOverride()
      expect(isOverridden()).toBe(true)
      expect(shouldBlockOAuth(IN_APP[0][1])).toBeNull()
    } finally {
      if (original) Object.defineProperty(window, 'sessionStorage', original)
    }
  })
})
