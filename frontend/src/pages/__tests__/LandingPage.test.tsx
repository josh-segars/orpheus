import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import { LandingPage } from '../LandingPage'

// Mock the waitlist hook so the page never touches Supabase. The mutation
// object is mutable per-test so we can drive idle / success states.
const mutate = vi.fn()
let mockMutation: {
  mutate: typeof mutate
  isPending: boolean
  isError: boolean
  isSuccess: boolean
  data?: { email: string }
}

vi.mock('../../hooks/useWaitlist', () => ({
  useJoinWaitlist: () => mockMutation,
}))

beforeEach(() => {
  mutate.mockReset()
  mockMutation = {
    mutate,
    isPending: false,
    isError: false,
    isSuccess: false,
  }
})

describe('LandingPage', () => {
  it('renders the hero, about dimensions, pricing, and waitlist sections', () => {
    render(<LandingPage />)
    expect(screen.getByText(/Make yours/i)).toBeInTheDocument()
    expect(screen.getByText('Profile Clarity')).toBeInTheDocument()
    expect(screen.getByText('Alignment')).toBeInTheDocument()
    // Closed-beta framing, not a price.
    expect(screen.getByText(/Currently in closed beta/i)).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: /Express Interest/i }),
    ).toBeInTheDocument()
  })

  it('points every sign-in link at the app host', () => {
    render(<LandingPage />)
    const signIns = screen.getAllByRole('link', { name: /^Sign in$/i })
    expect(signIns.length).toBeGreaterThan(0)
    signIns.forEach((link) =>
      expect(link).toHaveAttribute(
        'href',
        'https://app.orpheussocial.com/login',
      ),
    )
  })

  function fillForm(overrides: {
    first?: string
    last?: string
    email?: string
    beta?: boolean
    workshop?: boolean
  }) {
    const { first, last, email, beta, workshop } = overrides
    if (first !== undefined)
      fireEvent.change(screen.getByLabelText(/first name/i), {
        target: { value: first },
      })
    if (last !== undefined)
      fireEvent.change(screen.getByLabelText(/last name/i), {
        target: { value: last },
      })
    if (email !== undefined)
      fireEvent.change(screen.getByLabelText(/email address/i), {
        target: { value: email },
      })
    if (beta) fireEvent.click(screen.getByLabelText(/beta access/i))
    if (workshop) fireEvent.click(screen.getByLabelText(/live workshop/i))
  }

  const submit = () =>
    fireEvent.click(screen.getByRole('button', { name: /Express Interest/i }))

  it('does not submit when required fields are missing', () => {
    render(<LandingPage />)
    fillForm({ first: 'Josh', last: 'Segars', email: 'not-an-email', beta: true })
    submit()
    expect(mutate).not.toHaveBeenCalled()
    expect(screen.getByText(/valid email address/i)).toBeInTheDocument()
  })

  it('requires at least one interest', () => {
    render(<LandingPage />)
    fillForm({ first: 'Josh', last: 'Segars', email: 'josh@ess3.ai' })
    submit()
    expect(mutate).not.toHaveBeenCalled()
    expect(screen.getByText(/at least one interest/i)).toBeInTheDocument()
  })

  it('submits the full form to the waitlist mutation', () => {
    render(<LandingPage />)
    fillForm({
      first: 'Josh',
      last: 'Segars',
      email: 'josh@ess3.ai',
      beta: true,
      workshop: true,
    })
    submit()
    expect(mutate).toHaveBeenCalledWith({
      firstName: 'Josh',
      lastName: 'Segars',
      email: 'josh@ess3.ai',
      interests: ['beta_access', 'live_workshop'],
    })
  })

  it('shows the success state after joining', () => {
    mockMutation = {
      mutate,
      isPending: false,
      isError: false,
      isSuccess: true,
      data: { email: 'josh@ess3.ai' },
    }
    render(<LandingPage />)
    expect(screen.getByText(/on the list/i)).toBeInTheDocument()
    expect(screen.getByText('josh@ess3.ai')).toBeInTheDocument()
  })
})
