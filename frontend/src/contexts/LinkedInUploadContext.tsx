import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

/**
 * Holds the LinkedIn ZIP + XLSX `File` objects between Step 1, Step 2, and
 * the Groundwork "My Groundwork is Complete" submit. Files live in memory
 * for the lifetime of the React tree — a hard refresh clears them and the
 * client has to re-pick from disk. We intentionally don't persist the
 * bytes (IndexedDB / OPFS) for this beta because the user's local file
 * system already has them and the re-pick UX is brief.
 *
 * The Groundwork checklist's per-item completion for these two items is
 * derived from `archive !== null` / `analytics !== null` (see
 * GroundworkPage). That keeps state consistent: if a refresh drops the
 * Files, the corresponding checkmarks disappear too.
 */
export interface LinkedInUploadState {
  archive: File | null
  analytics: File | null
  setArchive: (file: File | null) => void
  setAnalytics: (file: File | null) => void
  clear: () => void
}

const LinkedInUploadContext = createContext<LinkedInUploadState | null>(null)

export function LinkedInUploadProvider({ children }: { children: ReactNode }) {
  const [archive, setArchiveState] = useState<File | null>(null)
  const [analytics, setAnalyticsState] = useState<File | null>(null)

  const setArchive = useCallback((file: File | null) => {
    setArchiveState(file)
  }, [])
  const setAnalytics = useCallback((file: File | null) => {
    setAnalyticsState(file)
  }, [])
  const clear = useCallback(() => {
    setArchiveState(null)
    setAnalyticsState(null)
  }, [])

  const value = useMemo(
    () => ({ archive, analytics, setArchive, setAnalytics, clear }),
    [archive, analytics, setArchive, setAnalytics, clear],
  )

  return (
    <LinkedInUploadContext.Provider value={value}>
      {children}
    </LinkedInUploadContext.Provider>
  )
}

export function useLinkedInUpload(): LinkedInUploadState {
  const ctx = useContext(LinkedInUploadContext)
  if (!ctx) {
    throw new Error(
      'useLinkedInUpload must be used inside <LinkedInUploadProvider>',
    )
  }
  return ctx
}
