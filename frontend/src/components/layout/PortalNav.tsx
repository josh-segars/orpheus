import { useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { useAdvisorClients } from '../../hooks/useAdvisorClients'
import { useJob } from '../../hooks/useJob'
import { useSessionRoles } from '../../hooks/useSessionRoles'
import { signOut, useSession } from '../../lib/auth'

interface LinkedInUserMetadata {
  name?: string
  given_name?: string
  family_name?: string
  picture?: string
}

/**
 * Top-of-portal nav. Renders an app-wide identity cluster on the right:
 *
 *   PREPARED FOR
 *   <Report subject's display name>           [avatar] [logout icon]
 *
 * Name source (ORPHEUS-52):
 *
 *   - Pure client on their own report     → their own LinkedIn `name`.
 *   - Advisor viewing a client's job      → that client's display_name,
 *                                            sourced from the advisor's
 *                                            GET /clients roster.
 *   - Dual-role advisor on self-report    → their own LinkedIn `name`
 *                                            (the matched client row has
 *                                            `is_self: true`).
 *   - Routes without `:jobId` (Welcome,   → the signed-in user's own
 *     Groundwork, /advisor/clients, etc.)   name. There is no "report
 *                                            subject" on those surfaces;
 *                                            self-attribution is the
 *                                            sensible default.
 *
 * The avatar stays from the prior dropdown implementation but the
 * dropdown menu itself is gone — sign-out is now a dedicated icon
 * button to the right of the avatar.
 */
export function PortalNav() {
  const { session } = useSession()
  const sessionRolesQuery = useSessionRoles()
  const navigate = useNavigate()
  const location = useLocation()
  const params = useParams()
  const [signingOut, setSigningOut] = useState(false)

  // Role flags drive the new (ORPHEUS-39) middle-of-nav tab toggle.
  // Both can be true (Andrew, dual-role) or just one (pure advisor,
  // pure client). The toggle only renders for advisors — clients
  // never need to switch surfaces.
  const roles = sessionRolesQuery.data
  const isAdvisor = Boolean(roles?.advisor_id)
  const isClient = Boolean(roles?.client_id)
  const onAdvisorSurface = location.pathname.startsWith('/advisor/')

  // Session-user-derived bits — the fallback for every name-source
  // branch below.
  const meta = (session?.user?.user_metadata ?? {}) as LinkedInUserMetadata
  const email = session?.user?.email ?? ''
  const sessionDisplayName = pickDisplayName(meta, email)
  const initials = pickInitials(meta, email)
  const picture = meta.picture

  // Look up the job's client_id when the current route carries one.
  // `useJob` is gated on `jobId` being truthy so this is a no-op on
  // routes like /welcome or /advisor/clients.
  const jobId = params.jobId
  const jobQuery = useJob(jobId)
  const jobClientId = jobQuery.data?.client_id ?? null

  // Advisor's roster — only fires for advisors (the hook gates on
  // isAdvisor internally). Used to resolve a job's client_id to a
  // human display_name, and to detect the dual-role "viewing my own
  // self-report" case via the matched row's `is_self` flag.
  const advisorClientsQuery = useAdvisorClients()
  const matchedAdvisorClient =
    isAdvisor && jobClientId
      ? advisorClientsQuery.data?.clients.find((c) => c.id === jobClientId)
      : undefined

  // Subject name = whose report this is. Decision tree:
  //
  //   1. Route has no jobId          → session user.
  //   2. Caller is not an advisor    → must be their own job (the
  //                                     /jobs/:id endpoint already
  //                                     enforces ownership), so session
  //                                     user.
  //   3. Caller is an advisor and    → advisor's own name (dual-role
  //      the matched client is_self    on self-report).
  //   4. Caller is an advisor and    → client's display_name from the
  //      the matched client is NOT     advisor roster.
  //      self
  //
  // While the advisor's roster or the job is still loading we fall
  // through to `sessionDisplayName` as a transient placeholder. The
  // alternative (rendering nothing) caused a layout shift on first
  // paint for advisors landing directly on /jobs/:id.
  let subjectDisplayName = sessionDisplayName
  if (jobId && isAdvisor && matchedAdvisorClient && !matchedAdvisorClient.is_self) {
    subjectDisplayName = matchedAdvisorClient.display_name
  }

  const handleSignOut = async () => {
    setSigningOut(true)
    try {
      await signOut()
    } finally {
      // useSession will react to SIGNED_OUT, but we navigate explicitly so
      // the user lands on /login instead of waiting for the next render.
      navigate('/login', { replace: true })
    }
  }

  return (
    <nav className="nav">
      <div className="wordmark">
        <span className="wordmark-orpheus">Orpheus</span>
        <span className="wordmark-social">Social</span>
      </div>
      {/*
        Role-aware middle nav (ORPHEUS-39).
        - Dual-role users (advisor + client, e.g. Andrew): two-tab
          toggle between Manage clients and My report. Active tab
          tracks the current pathname.
        - Advisor-only users: a single "Manage clients" pill — no
          toggle, just an active label. There's nowhere else to go
          and showing a disabled "My report" tab would mislead.
        - Client-only users: nothing rendered, current behaviour
          preserved.
      */}
      {isAdvisor && isClient && (
        <div className="nav-role-tabs" role="tablist" aria-label="Portal surface">
          <Link
            to="/advisor/clients"
            role="tab"
            aria-selected={onAdvisorSurface}
            className={
              onAdvisorSurface
                ? 'nav-role-tab nav-role-tab-active'
                : 'nav-role-tab'
            }
          >
            Manage clients
          </Link>
          <Link
            to="/"
            role="tab"
            aria-selected={!onAdvisorSurface}
            className={
              onAdvisorSurface
                ? 'nav-role-tab'
                : 'nav-role-tab nav-role-tab-active'
            }
          >
            My report
          </Link>
        </div>
      )}
      {isAdvisor && !isClient && (
        <div className="nav-role-tabs">
          <span className="nav-role-tab nav-role-tab-active">
            Manage clients
          </span>
        </div>
      )}
      <div className="nav-client">
        <span
          className="nav-client-text"
          aria-label={`Prepared for ${subjectDisplayName}`}
        >
          <span className="nav-client-label">Prepared for</span>
          <span className="nav-client-name">{subjectDisplayName}</span>
        </span>
        <span className="nav-client-avatar" aria-hidden="true">
          {picture ? (
            <img src={picture} alt="" referrerPolicy="no-referrer" />
          ) : (
            <span className="nav-client-initials">{initials}</span>
          )}
        </span>
        <button
          type="button"
          className="nav-logout-button"
          onClick={handleSignOut}
          disabled={signingOut}
          aria-label="Sign out"
          title="Sign out"
        >
          <LogoutIcon />
        </button>
      </div>
    </nav>
  )
}

/**
 * 24×24 logout glyph — door + arrow exiting to the right. Inline SVG
 * avoids the need to add an icon library (lucide-react etc.) for a
 * single occurrence; the existing nav SVGs in this app are all inline
 * for the same reason.
 */
function LogoutIcon() {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
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
