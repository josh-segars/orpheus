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
import { render, screen, fireEvent } from '@testing-library/react'
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

function clickComplete() {
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
    // Advisory only — the submit button stays enabled.
    expect(
      screen.getByRole('button', { name: /groundwork is complete/i }),
    ).not.toBeDisabled()
  })

  it('shows no large-archive advisory for a normal-sized archive', () => {
    renderPage()
    expect(screen.queryByText(/archive is large/i)).not.toBeInTheDocument()
  })
})
