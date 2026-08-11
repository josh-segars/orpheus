import { useEffect } from 'react'
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
 * or a bare URL.
 *
 * Structure is the canonical `nav / main / footer` column every other
 * screen uses — the body/#root flex layout centers those three and caps
 * nav/footer at 1200px, so a page that wraps them in its own shell
 * (the first version of this file did) renders visibly off-brand
 * chrome. The nav carries only the wordmark: the account dropdown and
 * survey link need a session, and these pages must render signed-out.
 *
 * The scroll reset exists because the most common entry is the footer
 * link at the very bottom of a long page — react-router preserves
 * scroll position across client-side navigations, so without it the
 * document opens scrolled to wherever the footer was.
 *
 * The document text itself lives in src/content/legal/*.md — the
 * canonical, versioned record the ToS §19 change-notice obligation
 * requires.
 */

interface LegalDocumentPageProps {
  markdown: string
}

export function LegalDocumentPage({ markdown }: LegalDocumentPageProps) {
  useEffect(() => {
    try {
      window.scrollTo(0, 0)
    } catch {
      // jsdom / exotic embedders — a no-op scroll is fine.
    }
  }, [markdown])

  return (
    <>
      <nav className="nav">
        <Link
          to="/"
          className="legal-nav-home"
          aria-label="Orpheus Social home"
        >
          <div className="wordmark">
            <span className="wordmark-orpheus">Orpheus</span>
            <span className="wordmark-social">Social</span>
          </div>
        </Link>
      </nav>
      <main className="main-interior">
        <article className="legal-document">
          {renderLegalMarkdown(markdown)}
        </article>
      </main>
      <PortalFooter />
    </>
  )
}
