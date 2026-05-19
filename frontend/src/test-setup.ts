/**
 * Vitest setup file — registered via vite.config.ts `test.setupFiles`.
 *
 * Two responsibilities (see ORPHEUS-47):
 *
 *   1. Extend Vitest's `expect` with @testing-library/jest-dom matchers
 *      (`toBeInTheDocument`, `toHaveAttribute`, etc.). Importing the
 *      package for its side effects is the documented pattern.
 *
 *   2. Run @testing-library/react's `cleanup` after every test so
 *      DOM nodes from a render don't leak into the next test. Vitest
 *      does NOT auto-cleanup the way Jest does — the
 *      VITEST_UNIT_CLEANUP env var is the only opt-out and we never
 *      want it set.
 *
 * If you need to extend this for global mocks (e.g. window.matchMedia
 * stubs for components that read media queries), add them here rather
 * than in individual test files.
 */
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
})
