/**
 * Consent carrier — ORPHEUS-126.
 *
 * The ToS/Privacy acceptance is given on /login, before there is any
 * authenticated identity to attach it to, so it has to survive the LinkedIn
 * OAuth round trip. Per ORPHEUS-92 the URL query string is the primary
 * carrier and sessionStorage the same-context fallback; these tests pin both
 * halves plus the address-bar cleanup.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
  CURRENT_PRIVACY_VERSION,
  CURRENT_TERMS_VERSION,
  buildAcceptanceRedirectUrl,
  captureTermsAcceptanceFromUrl,
  clearPendingTermsAcceptance,
  readPendingTermsAcceptance,
  withAcceptanceParams,
  writePendingTermsAcceptance,
} from '../consent'

beforeEach(() => {
  sessionStorage.clear()
  window.history.replaceState({}, '', '/')
})

afterEach(() => {
  sessionStorage.clear()
  window.history.replaceState({}, '', '/')
})

describe('buildAcceptanceRedirectUrl', () => {
  it('carries both versions on the redirect URL', () => {
    const url = new URL(buildAcceptanceRedirectUrl('https://app.example.com'))
    expect(url.pathname).toBe('/')
    expect(url.searchParams.get('terms_v')).toBe(CURRENT_TERMS_VERSION)
    expect(url.searchParams.get('privacy_v')).toBe(CURRENT_PRIVACY_VERSION)
  })
})

describe('withAcceptanceParams', () => {
  // ORPHEUS-132: /invite/:token and /signup return to routes that already
  // carry their own baggage. Stamping the versions must add to that, not
  // replace it — an invitation token lost here is an unusable link.
  it('adds both versions without disturbing existing params', () => {
    const url = withAcceptanceParams(
      new URL('https://app.example.com/invite/callback?token=abc123'),
    )
    expect(url.pathname).toBe('/invite/callback')
    expect(url.searchParams.get('token')).toBe('abc123')
    expect(url.searchParams.get('terms_v')).toBe(CURRENT_TERMS_VERSION)
    expect(url.searchParams.get('privacy_v')).toBe(CURRENT_PRIVACY_VERSION)
  })

  it('stamps the versions the capture side actually reads back', () => {
    // Closes the loop the shared helper exists to protect: whatever keys
    // withAcceptanceParams writes, captureTermsAcceptanceFromUrl must
    // recognise. A drift between the two would silently drop consent.
    const url = withAcceptanceParams(new URL('https://app.example.com/x'))
    window.history.replaceState({}, '', `/x${url.search}`)
    expect(captureTermsAcceptanceFromUrl()).toEqual({
      termsVersion: CURRENT_TERMS_VERSION,
      privacyVersion: CURRENT_PRIVACY_VERSION,
    })
  })
})

describe('pending acceptance storage', () => {
  it('round-trips through sessionStorage', () => {
    writePendingTermsAcceptance({
      termsVersion: '2026-08-11',
      privacyVersion: '2026-08-11',
    })
    expect(readPendingTermsAcceptance()).toEqual({
      termsVersion: '2026-08-11',
      privacyVersion: '2026-08-11',
    })
    clearPendingTermsAcceptance()
    expect(readPendingTermsAcceptance()).toBeNull()
  })

  it('returns null for a corrupt stored value rather than throwing', () => {
    sessionStorage.setItem('orpheus.pendingTermsAcceptance', 'not-json')
    expect(readPendingTermsAcceptance()).toBeNull()
  })

  it('returns null when only one version is present', () => {
    sessionStorage.setItem(
      'orpheus.pendingTermsAcceptance',
      JSON.stringify({ termsVersion: '2026-08-11' }),
    )
    expect(readPendingTermsAcceptance()).toBeNull()
  })
})

describe('captureTermsAcceptanceFromUrl', () => {
  it('captures both versions off the URL and stashes them', () => {
    window.history.replaceState(
      {},
      '',
      '/?terms_v=2026-08-11&privacy_v=2026-08-11',
    )
    const captured = captureTermsAcceptanceFromUrl()
    expect(captured).toEqual({
      termsVersion: '2026-08-11',
      privacyVersion: '2026-08-11',
    })
    expect(readPendingTermsAcceptance()).toEqual(captured)
  })

  it('strips its own params from the address bar so a refresh cannot replay', () => {
    window.history.replaceState(
      {},
      '',
      '/?terms_v=2026-08-11&privacy_v=2026-08-11',
    )
    captureTermsAcceptanceFromUrl()
    expect(window.location.search).toBe('')
    expect(window.location.pathname).toBe('/')
  })

  it('preserves unrelated query params while stripping its own', () => {
    window.history.replaceState(
      {},
      '',
      '/?terms_v=2026-08-11&privacy_v=2026-08-11&keep=me',
    )
    captureTermsAcceptanceFromUrl()
    expect(window.location.search).toBe('?keep=me')
  })

  it('is a no-op when the URL carries no acceptance', () => {
    window.history.replaceState({}, '', '/?foo=bar')
    expect(captureTermsAcceptanceFromUrl()).toBeNull()
    expect(readPendingTermsAcceptance()).toBeNull()
    // Untouched — we only rewrite the URL when we actually captured.
    expect(window.location.search).toBe('?foo=bar')
  })

  it('requires BOTH versions — a half-present carrier is not an acceptance', () => {
    window.history.replaceState({}, '', '/?terms_v=2026-08-11')
    expect(captureTermsAcceptanceFromUrl()).toBeNull()
    expect(readPendingTermsAcceptance()).toBeNull()
  })

  it('preserves the hash fragment — the OAuth tokens live there (2026-08-11 sign-in loop)', () => {
    // Supabase's implicit flow returns the session in the fragment:
    //   /?terms_v=…&privacy_v=…#access_token=…&refresh_token=…
    // and parses it asynchronously AFTER this module-load-time capture
    // runs. The original implementation rebuilt the URL without the
    // hash, erasing the tokens before they were ever read — every fresh
    // production sign-in bounced back to /login. The fragment must
    // survive the strip.
    window.history.replaceState(
      {},
      '',
      '/?terms_v=2026-08-11&privacy_v=2026-08-11#access_token=tok123&refresh_token=ref456',
    )
    const captured = captureTermsAcceptanceFromUrl()
    expect(captured).toEqual({
      termsVersion: '2026-08-11',
      privacyVersion: '2026-08-11',
    })
    expect(window.location.search).toBe('')
    expect(window.location.hash).toBe(
      '#access_token=tok123&refresh_token=ref456',
    )
  })
})
