import { Link } from 'react-router-dom'

import { PortalFooter } from '../../components/layout/PortalFooter'
import { renderLegalMarkdown } from '../../lib/legalMarkdown'
import './LegalDocumentPage.css'

/**
 * Shared shell for the published legal documents (ORPHEUS-125).
 *
 * These pages are PUBLIC on both hosts: registered in the marketing
 * branch (www / apex) and in the portal's unauthenticated section, so
 * GDPR Arts. 12-13's "provided at the point of collection" is satisfied
 * wherever the reader arrives from — the login checkbox, either footer,
 * or a bare URL. No PortalLayout (that assumes a session); a minimal
 * wordmark header + the document + the shared footer.
 *
 * The document text itself lives in src/content/legal/*.md — the
 * canonical, versioned record the ToS §19 change-notice obligation
 * requires. Render is at module scope, not per mount: the markdown is
 * static, so parsing once at import time keeps navigation to the page
 * free of re-parse work.
 */

interface LegalDocumentPageProps {
  markdown: string
}

export function LegalDocumentPage({ markdown }: LegalDocumentPageProps) {
  return (
    <div className="legal-shell">
      <header className="legal-header">
        <Link to="/" className="legal-wordmark" aria-label="Orpheus Social home">
          <span className="wordmark-sm-orpheus">Orpheus</span>
          <span className="wordmark-sm-social">Social</span>
        </Link>
      </header>
      <main className="legal-document">{renderLegalMarkdown(markdown)}</main>
      <PortalFooter />
    </div>
  )
}
