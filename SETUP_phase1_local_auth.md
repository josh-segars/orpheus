# Phase 1 Setup — Local Supabase + Dev LinkedIn App

Walkthrough for **ORPHEUS-24**. Do these steps in order; each section takes 2–10 minutes. At the end a placeholder "Continue with LinkedIn" button should round-trip through LinkedIn and land back on localhost.

---

## 1. Install prerequisites

```sh
# Docker Desktop — visit https://www.docker.com/products/docker-desktop
# and install for your platform. Launch it once so the daemon is running.

# Supabase CLI. Install varies by platform — DO NOT use `npm i -g supabase`,
# Supabase explicitly blocks global npm install (deliberate, not a bug).
#   macOS:    brew install supabase/tap/supabase
#   Windows:  scoop bucket add supabase https://github.com/supabase/scoop-bucket.git
#             scoop install supabase
#   Linux:    see https://github.com/supabase/cli#install-the-cli
# Project-local alternative on any platform: `npm i -D supabase`, then
# prefix every invocation with `npx` (e.g. `npx supabase start`).

# Verify
docker --version
supabase --version
```

Supabase CLI needs Docker to be running before `supabase start`. If Docker Desktop isn't open, `supabase start` will hang on the Postgres container.

---

## 2. Create the dev LinkedIn app

1. Go to **https://www.linkedin.com/developers/apps** and click **Create app**.
2. Fill in:
   - **App name.** `Orpheus Social — Dev`
   - **LinkedIn Page.** Use any page you manage; LinkedIn requires one, but nothing about this affects OIDC.
   - **App logo.** Any square image works; we'll replace it for the prod app.
   - **Legal agreement.** Accept.
3. Once created, go to the **Products** tab and request **Sign In with LinkedIn using OpenID Connect**. Approval is instant.
4. Go to the **Auth** tab.
   - Under **OAuth 2.0 settings** → **Authorized redirect URLs**, add exactly:
     ```
     http://127.0.0.1:54321/auth/v1/callback
     ```
   - Under **OAuth 2.0 scopes**, verify that `openid`, `profile`, and `email` are listed. They come with the OIDC product.
5. Still on the **Auth** tab, copy:
   - **Client ID** → `SUPABASE_AUTH_EXTERNAL_LINKEDIN_OIDC_CLIENT_ID`
   - **Primary Client Secret** → `SUPABASE_AUTH_EXTERNAL_LINKEDIN_OIDC_SECRET`

Keep these two values open in a password manager or scratch pad — you'll paste them in Step 3.

---

## 3. Configure env vars locally

From the repo root:

```sh
# Copy the env example templates
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
```

Open `backend/.env` and fill in:

```
SUPABASE_URL=                # leave blank for now — Step 4 prints it
SUPABASE_SERVICE_KEY=        # leave blank for now — Step 4 prints it
SUPABASE_ANON_KEY=           # leave blank for now — Step 4 prints it
ANTHROPIC_API_KEY=sk-ant-... # your existing key
ADMIN_EMAILS=andrew@segarsadvisory.com,josh@segarsfamily.com
FRONTEND_ORIGINS=http://localhost:5173
SUPABASE_AUTH_EXTERNAL_LINKEDIN_OIDC_CLIENT_ID=<paste from Step 2>
SUPABASE_AUTH_EXTERNAL_LINKEDIN_OIDC_SECRET=<paste from Step 2>
```

Open `frontend/.env.local` and fill in:

```
VITE_SUPABASE_URL=http://127.0.0.1:54321
VITE_SUPABASE_ANON_KEY=      # leave blank for now — Step 4 prints it
VITE_ADMIN_EMAILS=andrew@segarsadvisory.com,josh@segarsfamily.com
VITE_API_BASE_URL=http://localhost:8000
```

---

## 4. Start Supabase locally

The `supabase/config.toml` in this repo is already configured to enable the LinkedIn OIDC provider, wired to the env vars you just set. You don't need to run `supabase init`.

```sh
# From the repo root. First run pulls several Docker images (~2GB).
# Subsequent starts are instant.
set -a; source backend/.env; set +a    # loads the LinkedIn env vars
supabase start
```

When it's done, it prints something like:

```
Started supabase local development setup.

         API URL: http://127.0.0.1:54321
     GraphQL URL: http://127.0.0.1:54321/graphql/v1
          DB URL: postgresql://postgres:postgres@127.0.0.1:54322/postgres
      Studio URL: http://127.0.0.1:54323
    Inbucket URL: http://127.0.0.1:54324
      JWT secret: super-secret-jwt-token-with-at-least-32-characters
        anon key: eyJhbGciOi...
service_role key: eyJhbGciOi...
```

Copy the three keys into the right blanks:

- `SUPABASE_URL` (in `backend/.env`) = the **API URL**
- `SUPABASE_SERVICE_KEY` (in `backend/.env`) = the **service_role key**
- `SUPABASE_ANON_KEY` (in `backend/.env`) = the **anon key**
- `VITE_SUPABASE_ANON_KEY` (in `frontend/.env.local`) = the same **anon key**

If `supabase start` fails with a message about an unknown key under `[auth.external.linkedin_oidc]`, you likely have an older CLI. Upgrade with `npm i -g supabase@latest` and retry.

---

## 5. Open Supabase Studio and sanity-check

Open **http://127.0.0.1:54323** in your browser.

- Authentication → **Providers** — confirm **LinkedIn (OIDC)** is enabled.
- Authentication → **URL Configuration** — confirm the site URL is `http://localhost:5173`.

---

## 6. Smoke-test the LinkedIn round trip

We don't have the LoginPage yet (that ships in **ORPHEUS-28**), so use the Supabase Studio shortcut:

1. In Studio, go to **Authentication → Users → Add user → Log in with LinkedIn**.
2. The browser opens LinkedIn; authenticate.
3. You should be redirected back to Studio with a new user row visible.

If you see the new user row, the OAuth handshake is healthy and phase 1 is done.

Common failure modes:

- **"Redirect URI mismatch"** from LinkedIn → the callback URL on the LinkedIn app doesn't match `http://127.0.0.1:54321/auth/v1/callback` exactly (watch for `localhost` vs `127.0.0.1`).
- **"Invalid client credentials"** → secret was pasted with trailing whitespace, or you're using the dev app's client id with the prod app's secret.
- **Stuck on LinkedIn consent** → first-time LinkedIn sign-in asks for consent; click through it.

---

## 7. Close the loop on ORPHEUS-24

When the smoke test passes:

1. Commit the repo-side artifacts that landed in this pass:
   - `supabase/config.toml`
   - `backend/.env.example` updates
   - `frontend/.env.local.example`
   - `.gitignore` updates
   - This file (`SETUP_phase1_local_auth.md`)
2. Move **ORPHEUS-24** to **Done** in Plane.
3. Ping me and I'll pick up **ORPHEUS-26** (the `clients` table migration + trigger + FK).

---

## Reference

- Decision doc: `Decision_LinkedIn_Auth_2026-04-21.md` or **ORPHEUS-23**.
- Supabase CLI config reference: https://supabase.com/docs/guides/cli/config
- Supabase LinkedIn OIDC provider docs: https://supabase.com/docs/guides/auth/social-login/auth-linkedin
- LinkedIn OIDC scopes reference: https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2
