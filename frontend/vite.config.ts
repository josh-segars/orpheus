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
  },
})
