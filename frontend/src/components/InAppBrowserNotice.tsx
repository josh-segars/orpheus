import { useCallback, useState } from 'react'

import { MaterialIcon } from './icons/MaterialIcon'
import {
  type InAppBrowserInfo,
  setOverride,
  shouldBlockOAuth,
} from '../lib/inAppBrowser'
import '../pages/LoginPage.css'
import './InAppBrowserNotice.css'

/**
 * The in-app browser guard card (ORPHEUS-130).
 *
 * Replaces the sign-in action on /login, /signup and /invite/:token when
 * the page is being viewed inside an app's built-in browser, where the
 * LinkedIn OIDC hop cannot complete — see lib/inAppBrowser.ts for the
 * mechanism and the evidence.
 *
 * It is a hard block rather than an advisory banner [Josh, 2026-08-13].
 * The failure this prevents is invisible to the person experiencing it:
 * they get no error, no message, and no Orpheus screen — they simply
 * land back on a feed. Our first reporter burned four attempts before
 * telling anyone, and two other testers may have given up without
 * saying anything at all. A warning above a still-live button would have
 * been clicked straight through.
 *
 * The escape hatch is what makes the hard block defensible: detection is
 * a user-agent heuristic (again, see lib/inAppBrowser.ts), so "try
 * anyway" is always offered. It is styled quietly, not hidden — a user
 * who needs it must be able to find it, and a user who doesn't shouldn't
 * be tempted by it.
 *
 * Renders the whole `login-shell` / `login-card` scaffold rather than an
 * inner fragment, because it fully replaces all three pages and they
 * already share that shell.
 */

interface InAppBrowserNoticeProps {
  info: InAppBrowserInfo
  /** Re-render the host page after the override is recorded. */
  onContinueAnyway: () => void
}

/**
 * Per-platform gesture. Naming the actual affordance matters more than
 * usual here: the person is, by definition, in an app they didn't choose
 * to be in, looking for a menu they've probably never opened.
 */
function openInBrowserHint(platform: InAppBrowserInfo['platform']): string {
  switch (platform) {
    case 'ios':
      return 'Tap the ••• or share icon in the corner of this window, then choose "Open in Safari" (or "Open in browser").'
    case 'android':
      return 'Tap the ⋮ menu in the corner of this window, then choose "Open in browser" (or "Open in Chrome").'
    default:
      return 'Use this window\'s menu to reopen the page in Safari, Chrome, or another full browser.'
  }
}

/**
 * Put text on the clipboard, returning whether it landed.
 *
 * The async Clipboard API is unavailable or permission-blocked in a
 * good share of the very webviews this component targets, so the
 * execCommand path is a real fallback rather than legacy politeness. If
 * both fail we say so and leave the URL on screen to select by hand —
 * the address bar in these browsers is often not selectable, which is
 * precisely why the copy button exists.
 */
async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // Fall through to the legacy path.
  }

  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.setAttribute('readonly', '')
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(textarea)
    return ok
  } catch {
    return false
  }
}

export function InAppBrowserNotice({
  info,
  onContinueAnyway,
}: InAppBrowserNoticeProps) {
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>(
    'idle',
  )

  // The full current URL, so an invitation token or a ?code= prefill
  // survives the hop into the real browser. Losing it would turn a
  // one-tap fix into "ask your advisor to resend the invitation".
  const url = typeof window === 'undefined' ? '' : window.location.href

  const handleCopy = useCallback(async () => {
    const ok = await copyToClipboard(url)
    setCopyState(ok ? 'copied' : 'failed')
  }, [url])

  const handleContinueAnyway = useCallback(() => {
    setOverride()
    onContinueAnyway()
  }, [onContinueAnyway])

  return (
    <main className="login-shell">
      <div className="login-card">
        <div className="login-wordmark">
          <span className="wordmark-orpheus">Orpheus</span>
          <span className="wordmark-social">Social</span>
        </div>

        <h1 className="login-title">Open this page in your browser</h1>

        <p className="login-blurb">
          You&rsquo;re viewing this inside {info.name}&rsquo;s built-in
          browser, and LinkedIn sign-in can&rsquo;t finish here &mdash;
          it hands you back to the app instead of returning you to
          Orpheus. Opening the same link in Safari or Chrome takes about
          two taps and works normally.
        </p>

        <div className="inapp-steps">
          <div className="inapp-steps-label">How to switch</div>
          <ol className="inapp-steps-list">
            <li>{openInBrowserHint(info.platform)}</li>
            <li>
              If you don&rsquo;t see that option, copy the link below and
              paste it into your browser.
            </li>
          </ol>
        </div>

        <div className="inapp-link">
          <div className="inapp-link-url" title={url}>
            {url}
          </div>
          <button
            type="button"
            className="inapp-copy-button"
            onClick={() => {
              void handleCopy()
            }}
          >
            <MaterialIcon
              name={copyState === 'copied' ? 'check' : 'content_copy'}
              size={16}
            />
            {copyState === 'copied' ? 'Link copied' : 'Copy link'}
          </button>
          {copyState === 'failed' && (
            <p className="inapp-copy-failed" role="alert">
              We couldn&rsquo;t copy it automatically &mdash; select the
              address above and copy it by hand.
            </p>
          )}
        </div>

        <p className="login-fineprint">
          Orpheus uses your LinkedIn account only to verify who you are.
          We never post on your behalf.
        </p>

        {/*
          The escape hatch. Quiet, but present and plainly labelled: if
          the detection above is wrong, this is the only way past it.
        */}
        <button
          type="button"
          className="inapp-override"
          onClick={handleContinueAnyway}
        >
          Continue here anyway
        </button>
      </div>
    </main>
  )
}

/**
 * Guard state for a sign-in entry point.
 *
 * `blocked` is the detected host app, or null when the page should
 * render normally. `allowAnyway` records the override and re-renders the
 * caller.
 *
 * Pages that merely render a button only need `blocked` to swap their
 * markup; /invite/:token also needs it to suppress its mount-time
 * redirect into OAuth, which is why this is a value rather than a
 * wrapper component.
 */
export function useInAppBrowserGuard(): {
  blocked: InAppBrowserInfo | null
  allowAnyway: () => void
} {
  const [overridden, setOverridden] = useState(false)
  const blocked = overridden ? null : shouldBlockOAuth()
  const allowAnyway = useCallback(() => setOverridden(true), [])
  return { blocked, allowAnyway }
}
