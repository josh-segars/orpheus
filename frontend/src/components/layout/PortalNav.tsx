import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { isAdminEmail } from '../../hooks/useAdmin'
import { useSessionRoles } from '../../hooks/useSessionRoles'
import { signOut, useSession } from '../../lib/auth'

interface LinkedInUserMetadata {
  name?: string
  given_name?: string
  family_name?: string
  picture?: string
}

/**
 * Top-of-portal nav. Renders an app-wide identity cluster on the right
 * that doubles as the trigger for an account dropdown (ORPHEUS-71):
 *
 *   LOGGED IN AS
 *   <Signed-in user's own name>               [avatar]   ▸ (click to open)
 *
 * Identity reframe (ORPHEUS-71): the eyebrow is "Logged in as" + the
 * signed-in user's OWN name on every surface — no longer the report
 * subject. The report subject's name moved into the Signal Score hero.
 * This resolves the ORPHEUS-52 cross-surface oddity where "Prepared
 * for [own name]" read strangely on /advisor/clients and /admin, and
 * removes the per-route useJob / useAdvisorClients name resolution the
 * nav used to do.
 *
 * The dropdown consolidates what used to be three separate nav affordances:
 *   - Log Out (was the dedicated .nav-logout-button icon, ORPHEUS-52)
 *   - View Clients (was the .nav-role-tabs toggle, ORPHEUS-39)
 *   - View My Reports + Manage My Account (new)
 *
 * Items are role-conditional:
 *   - View My Reports → "/" (the SmartIndexRedirect routes a client or
 *     dual-role user to their own latest report). Client/dual-role only.
 *   - Manage My Account → /account placeholder (ORPHEUS-42 deferred).
 *     All roles.
 *   - Log Out → signOut(). All roles.
 *   - View Clients → /advisor/clients. Advisor / dual-role only.
 *   - Admin → /admin. Admin-allowlisted emails only.
 *
 * Interaction: click-to-open, close on outside-click + Escape, focus
 * returns to the trigger on Escape.
 */
export function PortalNav() {
  const { session } = useSession()
  const sessionRolesQuery = useSessionRoles()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [signingOut, setSigningOut] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)

  const roles = sessionRolesQuery.data
  const isAdvisor = Boolean(roles?.advisor_id)
  const isClient = Boolean(roles?.client_id)

  const meta = (session?.user?.user_metadata ?? {}) as LinkedInUserMetadata
  const email = session?.user?.email ?? ''
  const displayName = pickDisplayName(meta, email)
  const initials = pickInitials(meta, email)
  const picture = meta.picture
  const isAdmin = isAdminEmail(email)

  // Closed Beta feedback link (ORPHEUS-72). Rendered only when the env var
  // is set, so non-beta builds don't show a dangling button. URL is wired
  // via VITE_BETA_SURVEY_URL (mirror into Vercel); see .env.local.example.
  const surveyUrl = (import.meta.env.VITE_BETA_SURVEY_URL as string | undefined)?.trim()

  // Whether the privileged section (View Clients / Admin) renders at all.
  // Drives the divider so it never floats above an empty section.
  const hasPrivilegedSection = isAdvisor || isAdmin

  // Close on outside-click and Escape while the menu is open.
  useEffect(() => {
    if (!open) return

    function handlePointerDown(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false)
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  const handleSignOut = async () => {
    setSigningOut(true)
    setOpen(false)
    try {
      await signOut()
    } finally {
      // useSession reacts to SIGNED_OUT, but navigate explicitly so the
      // user lands on /login without waiting for the next render.
      navigate('/login', { replace: true })
    }
  }

  return (
    <nav className="nav">
      <div className="wordmark">
        <span className="wordmark-orpheus">Orpheus</span>
        <span className="wordmark-social">Social</span>
      </div>

      {surveyUrl && (
        <a
          className="nav-survey-link"
          href={surveyUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          Closed Beta Feedback
        </a>
      )}

      <div className="nav-account" ref={containerRef}>
        <button
          type="button"
          ref={triggerRef}
          className="nav-account-trigger"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-label={`Account menu for ${displayName}`}
          onClick={() => setOpen((prev) => !prev)}
        >
          <span className="nav-client-text">
            <span className="nav-client-label">Logged in as</span>
            <span className="nav-client-name">{displayName}</span>
          </span>
          <span className="nav-client-avatar" aria-hidden="true">
            {picture ? (
              <img src={picture} alt="" referrerPolicy="no-referrer" />
            ) : (
              <span className="nav-client-initials">{initials}</span>
            )}
          </span>
        </button>

        {open && (
          <div className="nav-account-menu" role="menu" aria-label="Account menu">
            {isClient && (
              <Link
                to="/"
                role="menuitem"
                className="nav-account-item"
                onClick={() => setOpen(false)}
              >
                View My Reports
              </Link>
            )}
            <Link
              to="/account"
              role="menuitem"
              className="nav-account-item"
              onClick={() => setOpen(false)}
            >
              Manage My Account
            </Link>
            <button
              type="button"
              role="menuitem"
              className="nav-account-item"
              onClick={handleSignOut}
              disabled={signingOut}
            >
              Log Out
            </button>

            {hasPrivilegedSection && (
              <div className="nav-account-divider" role="separator" />
            )}
            {isAdvisor && (
              <Link
                to="/advisor/clients"
                role="menuitem"
                className="nav-account-item"
                onClick={() => setOpen(false)}
              >
                View Clients
              </Link>
            )}
            {isAdmin && (
              <Link
                to="/admin"
                role="menuitem"
                className="nav-account-item"
                onClick={() => setOpen(false)}
              >
                Admin
              </Link>
            )}
          </div>
        )}
      </div>
    </nav>
  )
}

function pickDisplayName(meta: LinkedInUserMetadata, email: string): string {
  if (meta.name && meta.name.trim()) return meta.name.trim()
  const composed = [meta.given_name, meta.family_name]
    .filter((v): v is string => Boolean(v && v.trim()))
    .join(' ')
  if (composed) return composed
  if (email) return email.split('@')[0]
  return 'Signed in'
}

function pickInitials(meta: LinkedInUserMetadata, email: string): string {
  const first = meta.given_name?.trim()[0] ?? ''
  const last = meta.family_name?.trim()[0] ?? ''
  if (first || last) return (first + last).toUpperCase()
  if (meta.name) {
    const parts = meta.name.trim().split(/\s+/)
    const a = parts[0]?.[0] ?? ''
    const b = parts[parts.length - 1]?.[0] ?? ''
    if (a || b) return (a + b).toUpperCase()
  }
  if (email) return email.slice(0, 2).toUpperCase()
  return '·'
}
