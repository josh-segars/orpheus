import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { signOut, useSession } from '../../lib/auth'

interface LinkedInUserMetadata {
  name?: string
  given_name?: string
  family_name?: string
  picture?: string
}

/**
 * Top-of-portal nav. Reads the session via useSession() and renders the
 * client's LinkedIn picture / display name on the right with a sign-out
 * dropdown. Replaces the previous hardcoded "Jane Doe" placeholder.
 */
export function PortalNav() {
  const { session } = useSession()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const [signingOut, setSigningOut] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Close the dropdown when the user clicks outside it or hits Escape.
  useEffect(() => {
    if (!menuOpen) return
    const handleMouseDown = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setMenuOpen(false)
      }
    }
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('mousedown', handleMouseDown)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleMouseDown)
      document.removeEventListener('keydown', handleKey)
    }
  }, [menuOpen])

  const meta = (session?.user?.user_metadata ?? {}) as LinkedInUserMetadata
  const email = session?.user?.email ?? ''
  const displayName = pickDisplayName(meta, email)
  const initials = pickInitials(meta, email)
  const picture = meta.picture

  const handleSignOut = async () => {
    setMenuOpen(false)
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
      <div className="nav-client" ref={containerRef}>
        <button
          type="button"
          className="nav-client-trigger"
          onClick={() => setMenuOpen((o) => !o)}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          aria-label={`Account menu for ${displayName}`}
          disabled={signingOut}
        >
          <span className="nav-client-text">
            <span className="nav-client-label">Confidential Portal for</span>
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
        {menuOpen && (
          <div className="nav-client-menu" role="menu">
            {email && (
              <div className="nav-client-menu-email" aria-hidden="true">
                {email}
              </div>
            )}
            <button
              type="button"
              role="menuitem"
              className="nav-client-menu-item"
              onClick={handleSignOut}
            >
              Sign out
            </button>
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
