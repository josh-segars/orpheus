/**
 * GroundworkPage upload-failure UX — ORPHEUS-86.
 *
 * The "My Groundwork is Complete" submit posts the multipart /jobs upload.
 * Before this ticket, a transport-level death (the fetch promise rejecting
 * with "Failed to fetch" — the symptom when a large archive dies mid-transfer
 * at the edge) fell through to the generic `err.message` branch and surfaced
 * the opaque browser string to the client. Now:
 *   - a NetworkError maps to connection/large-archive guidance,
 *   - an ApiError still surfaces FastAPI's `{detail}`,
 *   - an unusually large archive shows a non-blocking advisory up front.
 *
 * Per the ORPHEUS-47 convention the data hooks are vi.mocked rather than
 * running an MSW server; useNavigate is stubbed so submit success is inert.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import { GroundworkPage } from '../GroundworkPage'
import { ApiError, NetworkError, UploadRejectedError } from '../../lib/apiClient'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => mockNavigate }
})

// Mutable hook returns — reassigned per test, reset in beforeEach.
let mockProgress: { data: unknown; isLoading: boolean }
let mockUpload: { archive: File | null; analytics: File | null; clear: () => void }
let mockMutateAsync: ReturnType<typeof vi.fn>
let mockIsPending = false

vi.mock('../../hooks/useGroundworkProgress', () => ({
  useGroundworkProgress: () => mockProgress,
}))
vi.mock('../../contexts/LinkedInUploadContext', () => ({
  useLinkedInUpload: () => mockUpload,
}))
vi.mock('../../hooks/useCreateJob', () => ({
  useCreateJob: () => ({ mutateAsync: mockMutateAsync, isPending: mockIsPending }),
}))

function makeFile(name: string, size: number): File {
  const f = new File(['x'], name)
  Object.defineProperty(f, 'size', { value: size })
  return f
}

const MB = 1024 * 1024

function renderPage() {
  return render(
    <MemoryRouter>
      <GroundworkPage />
    </MemoryRouter>,
  )
}

function consentCheckbox() {
  return screen.getByRole('checkbox', {
    name: /processing my linkedin data archive/i,
  })
}

/**
 * ORPHEUS-126: submit is gated on the upload-consent box as well as the
 * checklist, so every pre-existing submit case has to tick it first.
 */
function clickComplete() {
  const box = consentCheckbox()
  if (!(box as HTMLInputElement).checked) {
    fireEvent.click(box)
  }
  fireEvent.click(screen.getByRole('button', { name: /groundwork is complete/i }))
}

describe('GroundworkPage upload-failure UX (ORPHEUS-86)', () => {
  beforeEach(() => {
    mockNavigate.mockReset()
    mockMutateAsync = vi.fn()
    mockIsPending = false
    mockProgress = {
      data: { questionnaireComplete: true, latestPendingJobId: null },
      isLoading: false,
    }
    // Normal-sized files present so the button is enabled and no size
    // advisory fires unless a test overrides the archive.
    mockUpload = {
      archive: makeFile('archive.zip', 20 * MB),
      analytics: makeFile('analytics.xlsx', 1 * MB),
      clear: vi.fn(),
    }
  })

  it('shows actionable connection guidance when the upload dies at the transport level', async () => {
    mockMutateAsync.mockRejectedValue(new NetworkError('nope'))
    renderPage()
    clickComplete()
    expect(
      await screen.findByText(/couldn’t reach the server/i),
    ).toBeInTheDocument()
    // The raw browser string must not leak through.
    expect(screen.queryByText(/failed to fetch/i)).not.toBeInTheDocument()
  })

  it('shows the storage reason — not connection guidance — on a deterministic rejection (ORPHEUS-109)', async () => {
    mockMutateAsync.mockRejectedValue(
      new UploadRejectedError(
        'Your archive upload was rejected by storage.',
        400,
        'mime type application/x-zip-compressed is not supported',
      ),
    )
    renderPage()
    clickComplete()
    expect(
      await screen.findByText(/is not supported/i),
    ).toBeInTheDocument()
    expect(screen.getByText(/isn’t a connection problem/i)).toBeInTheDocument()
    // The misleading ORPHEUS-86 connection copy must not appear.
    expect(
      screen.queryByText(/couldn’t reach the server/i),
    ).not.toBeInTheDocument()
  })

  it('surfaces the API detail message on a rejected upload (ApiError)', async () => {
    mockMutateAsync.mockRejectedValue(
      new ApiError('POST /jobs failed: 422', 422, {
        detail: 'This looks like LinkedIn’s Basic data export.',
      }),
    )
    renderPage()
    clickComplete()
    expect(
      await screen.findByText(/Basic data export/i),
    ).toBeInTheDocument()
  })

  it('warns without blocking when the archive is unusually large', () => {
    mockUpload.archive = makeFile('archive.zip', 200 * MB)
    renderPage()
    expect(screen.getByText(/archive is large \(200 MB\)/i)).toBeInTheDocument()
    // The size advisory is exactly that — advisory. Tick the ORPHEUS-126
    // consent (the only other submit gate) and the button is live, which is
    // what "warns without blocking" has to mean now that consent exists.
    fireEvent.click(consentCheckbox())
    expect(
      screen.getByRole('button', { name: /groundwork is complete/i }),
    ).not.toBeDisabled()
  })

  it('shows no large-archive advisory for a normal-sized archive', () => {
    renderPage()
    expect(screen.queryByText(/archive is large/i)).not.toBeInTheDocument()
  })
})

// ── ORPHEUS-126: upload consent ────────────────────────────────────────

describe('GroundworkPage upload consent (ORPHEUS-126)', () => {
  beforeEach(() => {
    mockNavigate.mockReset()
    mockMutateAsync = vi.fn()
    mockIsPending = false
    mockProgress = {
      data: { questionnaireComplete: true, latestPendingJobId: null },
      isLoading: false,
    }
    mockUpload = {
      archive: makeFile('archive.zip', 20 * MB),
      analytics: makeFile('analytics.xlsx', 1 * MB),
      clear: vi.fn(),
    }
  })

  it('starts unticked even with every checklist item complete', () => {
    renderPage()
    expect(consentCheckbox()).not.toBeChecked()
  })

  it('keeps submit disabled until the consent is given', () => {
    renderPage()
    const button = screen.getByRole('button', {
      name: /groundwork is complete/i,
    })
    expect(button).toBeDisabled()
    fireEvent.click(consentCheckbox())
    expect(button).toBeEnabled()
  })

  it('explains WHY submit is disabled when only the consent is missing', () => {
    renderPage()
    // Otherwise a client who has finished everything reads "Available once
    // all items above are complete" next to a completed checklist.
    expect(
      screen.getByText(/confirm the permission above/i),
    ).toBeInTheDocument()
  })

  it('does not submit while unticked', () => {
    renderPage()
    fireEvent.click(
      screen.getByRole('button', { name: /groundwork is complete/i }),
    )
    expect(mockMutateAsync).not.toHaveBeenCalled()
  })

  it('passes the consent through to the submit', async () => {
    mockMutateAsync.mockResolvedValue({ id: 'job-1' })
    renderPage()
    clickComplete()

    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalled())
    expect(mockMutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ uploadConsent: true }),
    )
  })

  it('links the Privacy Policy in a new tab', () => {
    renderPage()
    const link = screen.getByRole('link', { name: /privacy policy/i })
    expect(link).toHaveAttribute('href', '/privacy')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('promises no retention window the system does not implement', () => {
    renderPage()
    // The Privacy Policy's 30-day raw-upload deletion clause has no
    // sweeper behind it (2026-08-03 review). The copy must not restate it.
    expect(screen.queryByText(/30 days/i)).toBeNull()
    expect(
      screen.getByText(/kept until you delete your account/i),
    ).toBeInTheDocument()
  })
})
