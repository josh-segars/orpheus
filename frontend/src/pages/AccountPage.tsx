import { Link } from 'react-router-dom'

import { MaterialIcon } from '../components/icons/MaterialIcon'

/**
 * Placeholder for account management (ORPHEUS-71 → ORPHEUS-42).
 *
 * "Manage My Account" in the nav dropdown points here. The real
 * account-management surface (profile, data, disconnect, deletion) is
 * ORPHEUS-42, which is beta-deferred. Rather than render the dropdown
 * item disabled, we route to this honest "coming soon" stub so the
 * affordance is discoverable and the route exists for ORPHEUS-42 to
 * fill in later.
 */
export function AccountPage() {
  return (
    <main className="main-interior">
      <div className="section-header">
        <div className="section-eyebrow">Account</div>
        <h2 className="section-title">Account management is on the way</h2>
        <p className="section-intro">
          This is where you&rsquo;ll manage your profile, your connected
          LinkedIn data, and your account during the beta. We&rsquo;re still
          building it &mdash; check back soon.
        </p>
      </div>
      <div className="actions">
        <Link to="/" className="btn-secondary">
          <MaterialIcon name="arrow_back" size={16} /> Back to my portal
        </Link>
      </div>
    </main>
  )
}
