import { useEffect, useRef } from 'react'
import { useMutation } from '@tanstack/react-query'

import { apiPostJson } from '../lib/apiClient'
import {
  clearPendingTermsAcceptance,
  readPendingTermsAcceptance,
  type PendingTermsAcceptance,
} from '../lib/consent'
import { useSession } from '../lib/auth'

interface RecordTermsAcceptanceResponse {
  recorded: boolean
  terms_version: string
  privacy_version: string
}

/**
 * Post the pending ToS/Privacy acceptance once the OAuth round trip has
 * produced an authenticated session (ORPHEUS-126).
 *
 * The user ticked the box on /login, before there was any identity to
 * attach the acceptance to. lib/consent.ts carried it across the redirect
 * and stashed it; this hook is the other end — it fires exactly once per
 * captured acceptance, as soon as a session exists.
 *
 * Failure posture: a failed post clears nothing, so the next authenticated
 * render retries. It never blocks or interrupts the user — they have
 * already performed the affirmative act, and holding the portal hostage to
 * our bookkeeping would punish them for our transient error. The cost of a
 * permanently failed record is an Art. 7(1) gap for that account, which is
 * why the endpoint is idempotent and the retry is cheap.
 */
export function useRecordTermsAcceptance(): void {
  const { status } = useSession()
  const attempted = useRef(false)

  const mutation = useMutation<
    RecordTermsAcceptanceResponse,
    Error,
    PendingTermsAcceptance
  >({
    mutationFn: (acceptance) =>
      apiPostJson<RecordTermsAcceptanceResponse>('/consent/terms', {
        terms_version: acceptance.termsVersion,
        privacy_version: acceptance.privacyVersion,
      }),
    onSuccess: () => {
      // Recorded (or already present) — stop carrying it.
      clearPendingTermsAcceptance()
    },
  })

  const { mutate } = mutation

  useEffect(() => {
    if (status !== 'authenticated') return
    if (attempted.current) return

    const pending = readPendingTermsAcceptance()
    if (!pending) return

    attempted.current = true
    mutate(pending)
  }, [status, mutate])
}

/**
 * Mount-only wrapper so App can run the recorder without every route
 * needing to know about it. Renders nothing.
 */
export function TermsAcceptanceRecorder(): null {
  useRecordTermsAcceptance()
  return null
}
