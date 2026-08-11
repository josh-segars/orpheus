/**
 * Legal document pages — /privacy and /terms (ORPHEUS-125).
 *
 * Three concerns pinned here:
 *
 *   1. The documents actually render from the committed markdown — real
 *      headings, tables, and text, with no markdown syntax leaking into
 *      the DOM (the bespoke renderer only understands a fixed dialect,
 *      so leakage is what a bad future edit looks like).
 *   2. The published effective date matches the consent version constants
 *      (ORPHEUS-126) — consent rows record acceptance against
 *      CURRENT_*_VERSION, so a date drift here would record consent to a
 *      document nobody could have read.
 *   3. The shared footer's legal links are real routes, not the
 *      href="#" placeholders this ticket retired, and the label is
 *      "Privacy Policy" (not the old "Confidentiality").
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import privacyMarkdown from '../../../content/legal/privacy.md?raw'
import termsMarkdown from '../../../content/legal/terms.md?raw'
import {
  CURRENT_PRIVACY_VERSION,
  CURRENT_TERMS_VERSION,
} from '../../../lib/consent'
import { PortalFooter } from '../../../components/layout/PortalFooter'
import { PrivacyPolicyPage } from '../PrivacyPolicyPage'
import { TermsOfServicePage } from '../TermsOfServicePage'

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

/** "2026-08-11" → "August 11, 2026", timezone-proof. */
function displayDate(isoVersion: string): string {
  return new Date(`${isoVersion}T00:00:00Z`).toLocaleDateString('en-US', {
    timeZone: 'UTC',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

describe('PrivacyPolicyPage', () => {
  it('renders the document with real structure, no markdown leakage', () => {
    renderWithRouter(<PrivacyPolicyPage />)

    expect(
      screen.getByRole('heading', { level: 1, name: /orpheus social privacy policy/i }),
    ).toBeInTheDocument()

    // A deep section renders as a heading, not text.
    expect(
      screen.getByRole('heading', { level: 2, name: /15\. cookies and similar technologies/i }),
    ).toBeInTheDocument()

    // The sub-processor table renders as a table with its rows.
    expect(
      screen.getByRole('columnheader', { name: /sub-processor/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: /anthropic, pbc/i })).toBeInTheDocument()

    // No raw markdown tokens survive into the DOM.
    const main = screen.getByRole('main')
    expect(main.textContent).not.toContain('**')
    expect(main.textContent).not.toContain('](')
    expect(main.textContent).not.toContain('| ---')
  })

  it('carries the effective date the consent version records (ORPHEUS-126 pairing)', () => {
    renderWithRouter(<PrivacyPolicyPage />)
    expect(
      screen.getByText(new RegExp(`last updated: ${displayDate(CURRENT_PRIVACY_VERSION)}`, 'i')),
    ).toBeInTheDocument()
  })
})

describe('TermsOfServicePage', () => {
  it('renders the document with real structure, no markdown leakage', () => {
    renderWithRouter(<TermsOfServicePage />)

    expect(
      screen.getByRole('heading', { level: 1, name: /orpheus social terms of service/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: /19\. changes to these terms/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 3, name: /17\.4 class-action waiver/i }),
    ).toBeInTheDocument()

    const main = screen.getByRole('main')
    expect(main.textContent).not.toContain('**')
    expect(main.textContent).not.toContain('](')
  })

  it('carries the effective date the consent version records (ORPHEUS-126 pairing)', () => {
    renderWithRouter(<TermsOfServicePage />)
    expect(
      screen.getByText(new RegExp(`last updated: ${displayDate(CURRENT_TERMS_VERSION)}`, 'i')),
    ).toBeInTheDocument()
  })
})

describe('committed markdown ↔ consent version pairing (source level)', () => {
  // Belt to the render tests' braces: assert against the raw files too,
  // so a renderer bug can't mask a date drift.
  it('privacy.md and terms.md state the exact dates the consent constants claim', () => {
    expect(privacyMarkdown).toContain(
      `Last updated: ${displayDate(CURRENT_PRIVACY_VERSION)}`,
    )
    expect(termsMarkdown).toContain(
      `Last updated: ${displayDate(CURRENT_TERMS_VERSION)}`,
    )
  })
})

describe('PortalFooter legal links (ORPHEUS-125)', () => {
  it('links Terms of Service and Privacy Policy to real routes — no placeholders, no "Confidentiality"', () => {
    renderWithRouter(<PortalFooter />)

    expect(screen.getByRole('link', { name: /terms of service/i })).toHaveAttribute(
      'href',
      '/terms',
    )
    expect(screen.getByRole('link', { name: /privacy policy/i })).toHaveAttribute(
      'href',
      '/privacy',
    )
    expect(screen.queryByText(/confidentiality/i)).not.toBeInTheDocument()
  })
})
