import termsMarkdown from '../../content/legal/terms.md?raw'

import { LegalDocumentPage } from './LegalDocumentPage'

/**
 * /terms — the published Terms of Service (ORPHEUS-125).
 *
 * Effective-date coupling: the "Last updated" date inside the markdown
 * MUST match CURRENT_TERMS_VERSION in lib/consent.ts (and its backend
 * mirror) — see PrivacyPolicyPage for why. A test pins the pairing.
 */
export function TermsOfServicePage() {
  return <LegalDocumentPage markdown={termsMarkdown} />
}
