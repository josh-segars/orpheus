import privacyMarkdown from '../../content/legal/privacy.md?raw'

import { LegalDocumentPage } from './LegalDocumentPage'

/**
 * /privacy — the published Privacy Policy (ORPHEUS-125).
 *
 * Effective-date coupling: the "Last updated" date inside the markdown
 * MUST match CURRENT_PRIVACY_VERSION in lib/consent.ts (and its backend
 * mirror) — consent rows record acceptance against that version string,
 * so a date change here without a version bump records consent to a
 * document nobody could have read. A test pins the pairing.
 */
export function PrivacyPolicyPage() {
  return <LegalDocumentPage markdown={privacyMarkdown} />
}
