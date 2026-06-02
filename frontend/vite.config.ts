/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
  },
  // Vitest config — see ORPHEUS-47. jsdom env for React component tests;
  // globals enabled so test files don't need to import {describe,it,expect}.
  // setupFiles registers @testing-library/jest-dom matchers and the
  // afterEach(cleanup) hook so a stray render doesn't leak between tests.
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    css: false,
    // Stub the `import.meta.env` reads that fail-fast at module load
    // (apiClient.ts under ORPHEUS-54, supabase.ts pre-existing). Tests
    // mock the higher-level data hooks, but a stray import that drags
    // these modules in would otherwise crash before the test body runs.
    env: {
      VITE_API_BASE_URL: 'http://localhost:8000',
      VITE_SUPABASE_URL: 'http://127.0.0.1:54321',
      VITE_SUPABASE_ANON_KEY: 'test-anon-key',
    },
  },
})
