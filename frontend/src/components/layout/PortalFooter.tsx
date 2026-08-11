import { Link } from 'react-router-dom'

import { PRIVACY_PATH, TERMS_PATH } from '../../lib/consent'

/**
 * Shared footer. The legal links became real in ORPHEUS-125 — they were
 * `href="#"` placeholders from the prototype port. "Confidentiality" was
 * renamed "Privacy Policy" in the same pass: users look for those words,
 * and "Confidentiality" names a different thing.
 */
export function PortalFooter() {
  return (
    <footer className="footer">
      <div className="wordmark-sm">
        <span className="wordmark-sm-orpheus">Orpheus</span>
        <span className="wordmark-sm-social">Social</span>
      </div>
      <div className="footer-links">
        <Link to={TERMS_PATH}>Terms of Service</Link>
        <Link to={PRIVACY_PATH}>Privacy Policy</Link>
        <span>Copyright &copy; 2026 All Rights Reserved.</span>
      </div>
    </footer>
  )
}
