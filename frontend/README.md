# Orpheus Social — Frontend

React + TypeScript + Vite client portal. Talks to the FastAPI backend for
job submission, polling, and report rendering.

## First-time setup

```bash
# From frontend/
npm install

# Generate the MSW service worker (dev-only mock API).
# Creates public/mockServiceWorker.js — committed to git.
npx msw init public/ --save

# Typecheck (strict)
npm run typecheck

# Run the dev server (starts MSW automatically in dev mode)
npm run dev
```

Open http://localhost:5173 — the index route redirects to `/jobs/demo`,
which MSW serves from `src/mocks/fixtures/signalScoreJob.ts`.

## Against the real backend

Set `VITE_API_BASE_URL` to the FastAPI base URL. In dev, MSW will still
intercept matching paths; disable MSW by editing `src/main.tsx` if you
want real network calls in dev.

```bash
VITE_API_BASE_URL=https://api.orpheussocial.example npm run dev
```

## Layout

```
src/
├── App.tsx                          # Routes
├── main.tsx                         # Entry + providers + MSW bootstrap
├── components/layout/               # Shared nav / footer / portal shell
├── hooks/useJob.ts                  # TanStack Query hook, polls until complete
├── lib/apiClient.ts                 # Thin fetch wrapper
├── mocks/                           # MSW handlers + fixtures
├── pages/
│   ├── SignalScorePage.{tsx,css}    # Ported from orpheus-signal-score.html (v2)
│   └── NotFoundPage.tsx
└── types/                           # TS mirror of backend/models/*.py
```

Shared design tokens and primitives live in the repo-root
`orpheus-styles.css`, imported globally in `main.tsx`. Page-specific
styles live next to their page as `.css` files.

## Data contract

The Signal Score page expects `/jobs/:id` to return a `Job` (see
`src/types/job.ts`). When `state === 'complete'`, `result` contains:

- `scoring`: `ScoringStageOutput` — mirrors
  `backend/models/scoring.py` (v2 4-dimension architecture).
- `narratives`: `{ dimension_narratives, forward_brief }` — mirrors the
  JSON returned by `backend/agents/narrative.py`.

The MSW fixture uses v2 dimension names:

1. Profile Signal Clarity (35%)
2. Behavioral Signal Strength (30%)
3. Behavioral Signal Quality (20%)
4. Profile-Behavior Alignment (15%)

Note: the original `orpheus-signal-score.html` prototype was built
against the v1 model (5 dimensions: Presence / Reach / Resonance /
Consistency / Authority). This React port uses the v2 names and weights
described in `PRODUCT_CONTEXT.md`.
