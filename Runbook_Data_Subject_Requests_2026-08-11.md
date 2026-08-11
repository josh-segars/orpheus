# Runbook: Data-Subject Requests (erasure, access, portability)

**Refs ORPHEUS-127.** Written 2026-08-11; every query below was executed against the
production database that day (see "Testing evidence" at the end). If the schema has
changed since, re-verify before relying on this document — migration files under
`backend/migrations/` are the record of what changed.

Every data-subject right in Privacy Policy §12 (`/privacy`, canonical markdown at
`frontend/src/content/legal/privacy.md`) is fulfilled either by the in-product
deletion flow (ORPHEUS-124) or by hand, via `contact@orpheussocial.com`. Manual
fulfilment is fine under GDPR — what matters is doing it correctly and inside the
response clock. This document is the correct procedure. It assumes **no prior
knowledge of the schema**; the one thing you must internalize before touching
anything is the FK trap in the next section.

Legal decisions about a request (refusing one, charging a fee, an unusual
jurisdiction claim) are **Tim's call**. The mechanics below are Josh's.

---

## The FK trap — read this first

The obvious move for an erasure request — delete the user in the Supabase
dashboard's Auth section — is wrong in both directions:

| FK | Behavior on auth-user delete | Consequence |
|---|---|---|
| `clients.user_id → auth.users` | `ON DELETE SET NULL` (`001_base_schema.sql:127`) | The clients row and **every** downstream `jobs` / `ingested_data` / `scores` / `narratives` / `questionnaire_responses` / `reports` row survives, orphaned — and is now *harder* to find because the link to the person is gone. The opposite of erasure. |
| `advisors.user_id → auth.users` | `ON DELETE CASCADE` (`:104`) | The advisors row dies… |
| `clients.advisor_id → advisors` | `ON DELETE CASCADE` (`:126`) | …and takes the advisor's **entire client roster** — other people's reports — with it. Far too much. |
| Storage objects `uploads/{client_id}/…` | No FK at all | Survive any database delete. Must be swept explicitly. |
| `terms_acceptances.user_id → auth.users` | `ON DELETE CASCADE` (`020_consent_records.sql`) | The one cascade that is *correct* on auth-user delete — consent records go with the account, deliberately (see 020's header). |

So: **the auth user is always deleted last**, after the business rows have been
removed explicitly, and **an advisor's auth user is never deleted while their
roster is non-empty**. This is exactly the order the shipped self-service handler
uses — `backend/routers/account.py` is the executable twin of section 3 below and
its module docstring is the extended rationale.

## Where to run the SQL

- **Supabase SQL editor** — https://supabase.com/dashboard/project/yqxuddkixzjruxtdjxpr
  (project ref `yqxuddkixzjruxtdjxpr`; login pointer in `CREDENTIALS.md`). Runs as
  `postgres`, bypasses RLS — which is required; most of these tables are
  read-restricted to the row owner.
- **Supabase MCP** from a Claude session (`mcp__supabase__execute_sql`) — equivalent
  access, and how this runbook was tested.

Queries use `'REQUESTER_EMAIL'` and `'…_ID'` placeholders — find/replace before
running. Nothing here is parameterized; the SQL editor has no bind variables.

---

## 1. Intake and identity verification

Requests arrive at `contact@orpheussocial.com` (§12.5). On receipt:

1. **Log it immediately** (section 8) — the clock starts at receipt, not at verification.
2. **Verify identity** before disclosing or deleting anything. The normal method
   (§12.5): confirm the requester controls the LinkedIn account tied to their
   Orpheus account — ask them to sign in to the portal and confirm from inside, or
   reply from the email address on the account, or other reasonable means
   proportionate to the request (an access request warrants more care than a
   rectification of a typo). An **authorized agent** may submit on someone's
   behalf; require proof of authorization.
3. **Know the clock:**

| Regime | Deadline | Extension |
|---|---|---|
| GDPR / UK GDPR | 30 days from receipt | +2 months for complex requests, on notice within the first 30 days |
| CCPA / CPRA | 45 days | +45 days on notice |
| Other US state laws (§12.4) | Generally 45 days | Per statute; provide the appeal process where required |

The first request in any twelve-month period is free; repetitive or excessive
requests may be charged or refused where the law permits (§12.5) — that refusal is
Tim's call, and it gets logged like everything else.

## 2. Resolve who we hold data about

One email address can map to up to four kinds of record, and — proven in testing —
**the clients-row email can differ from the auth-account email** (advisory clients
are invited at one address but may sign in with a LinkedIn account registered to
another). Resolution therefore matches `clients` by *either* email or `user_id`:

```sql
WITH target AS (SELECT lower(trim('REQUESTER_EMAIL')) AS email),
auth_match AS (
    SELECT u.id, u.email, u.created_at, u.last_sign_in_at
    FROM auth.users u, target t WHERE lower(u.email) = t.email
)
SELECT 'auth_user' AS record, id::text, email, created_at::text FROM auth_match
UNION ALL
SELECT 'clients', c.id::text, c.email, c.created_at::text
FROM public.clients c, target t
WHERE lower(c.email) = t.email OR c.user_id IN (SELECT id FROM auth_match)
UNION ALL
SELECT 'advisors', a.id::text, u.email, a.created_at::text
FROM public.advisors a JOIN auth.users u ON u.id = a.user_id, target t
WHERE lower(u.email) = t.email
UNION ALL
SELECT 'waitlist', w.id::text, w.email, w.created_at::text
FROM public.waitlist w, target t WHERE lower(w.email) = t.email
UNION ALL
SELECT 'orphaned_clients', c.id::text, c.email, c.created_at::text
FROM public.clients c, target t
WHERE c.user_id IS NULL AND lower(c.email) = t.email;
```

Interpreting the shapes you'll see:

- **auth_user + clients (+ maybe advisors)** — a normal account holder. A row in
  both `clients` and `advisors` means a self-serve individual or an advisor with an
  `is_self` client row.
- **clients only, `user_id` NULL, invitation pending** — an advisory client who was
  invited but never signed in. There is no auth user to delete; only sections 3
  (steps 3–4) and 5 apply.
- **waitlist only** — a marketing-list prospect, never a user. Erasure is a single
  `DELETE FROM public.waitlist`; access is that one row.
- **orphaned_clients hits** — data whose link to a person was already severed (the
  SET-NULL trap fired at some point). Treat as belonging to the requester if the
  email matches; this arm exists precisely so such rows can't hide.
- **Nothing at all** — respond that we hold no personal data for that address, and
  log the request anyway.

Record every ID the query returns — the rest of the runbook consumes them as
`AUTH_USER_ID`, `CLIENT_ID`, `ADVISOR_ID`.

## 3. Erasure (GDPR Art. 17 / CCPA deletion)

### Path A — self-service (preferred)

If the person has a working account, point them at **Account page → Danger Zone →
Delete account** (ORPHEUS-124, live-validated in production 2026-08-07/10). It
performs every step below in the right order, including the storage sweep and the
`terms_acceptances` cascade, and it is blocked with a 409 for an advisor whose
roster still has other clients — in that case arrange the roster transfer/cleanup
first, exactly as the in-product message says.

Self-service is preferred not for convenience but because signing in *is* the
identity verification.

### Path B — manual

For a requester who can't or won't sign in, or an invited-never-signed-in client.
Order is load-bearing; each step's failure leaves a recoverable state, which is why
the auth user goes last.

**Step 0 — before-snapshot.** Capture what exists so step 4's verification has
something to compare against:

```sql
SELECT
  (SELECT count(*) FROM public.jobs WHERE client_id = 'CLIENT_ID')      AS jobs,
  (SELECT count(*) FROM public.questionnaire_responses WHERE client_id = 'CLIENT_ID') AS questionnaires,
  (SELECT count(*) FROM public.reports WHERE client_id = 'CLIENT_ID')   AS reports,
  (SELECT count(*) FROM public.narratives WHERE job_id IN
      (SELECT id FROM public.jobs WHERE client_id = 'CLIENT_ID'))       AS narratives,
  (SELECT count(*) FROM storage.objects WHERE bucket_id = 'uploads'
      AND name LIKE 'CLIENT_ID' || '/%')                                AS storage_objects,
  (SELECT count(*) FROM public.terms_acceptances WHERE user_id = 'AUTH_USER_ID') AS terms_acceptances;
```

**Step 1 — advisor-roster guard.** Skip if the person has no advisors row.
**STOP if this returns anything but zero** — deleting further would destroy other
people's reports. Roster transfer/cleanup first.

```sql
SELECT count(*) AS non_self_roster_clients
FROM public.clients c
WHERE c.advisor_id = 'ADVISOR_ID'
  AND c.user_id IS DISTINCT FROM 'AUTH_USER_ID'::uuid;
```

(For an advisor with no auth user, every roster row counts — the guard still holds.)

**Step 2 — storage sweep.** List what's there:

```sql
SELECT name, created_at, (metadata->>'size')::bigint AS bytes
FROM storage.objects
WHERE bucket_id = 'uploads' AND name LIKE 'CLIENT_ID' || '/%';
```

Delete the `{client_id}/` folder — **including any `staging/` prefix** (abandoned
uploads live there and nothing else ever removes them) — via the dashboard's
Storage browser (Storage → uploads). **Do not `DELETE FROM storage.objects` in
SQL**: that removes the index row but strands the underlying stored object.
Nothing in the database has been touched yet, so a failure here aborts cleanly.

**Step 3 — the clients row, explicitly.** Its `ON DELETE CASCADE` children
(`jobs` → `ingested_data`/`scores`/`narratives`, plus `questionnaire_responses`
and `reports`) go with it:

```sql
DELETE FROM public.clients WHERE id = 'CLIENT_ID' RETURNING id, email;
```

**Step 4 — the advisors row**, if there is one (safe now — the guard ran):

```sql
DELETE FROM public.advisors WHERE id = 'ADVISOR_ID' RETURNING id;
```

**Step 5 — the waitlist row.** Default: an erasure request covers it — delete it
unless the requester explicitly asks to stay on the interest list:

```sql
DELETE FROM public.waitlist WHERE lower(email) = lower('REQUESTER_EMAIL') RETURNING id;
```

**Step 6 — the auth user, LAST.** Supabase dashboard → Authentication → Users →
find by email → Delete user. This cascades `terms_acceptances` (correct — see the
FK table) and the LinkedIn identity. Doing this step first is the SET-NULL trap;
doing it last means any earlier failure leaves an intact, recoverable account
instead of an orphaned data set.

**Backups:** we do not surgically edit backups — the normal and accepted position.
Privacy Policy §10 says deletion from active systems is immediate and backups may
persist up to ninety (90) further days before being overwritten in the ordinary
course. Say this plainly in the completion reply if asked.

## 4. Verify it worked — the query that catches the trap

Run after **either** path. Every arm must come back zero; the `orphaned_clients`
arm is the one that catches the SET-NULL failure mode specifically.

```sql
WITH target AS (SELECT lower(trim('REQUESTER_EMAIL')) AS email)
SELECT 'orphaned_clients (SET-NULL trap)' AS check_name, count(*) AS residue
FROM public.clients c, target t WHERE c.user_id IS NULL AND lower(c.email) = t.email
UNION ALL
SELECT 'clients (any residue)', count(*) FROM public.clients c, target t WHERE lower(c.email) = t.email
UNION ALL
SELECT 'auth_user (any residue)', count(*) FROM auth.users u, target t WHERE lower(u.email) = t.email
UNION ALL
SELECT 'waitlist (any residue)', count(*) FROM public.waitlist w, target t WHERE lower(w.email) = t.email
UNION ALL
SELECT 'jobs (by captured id)', count(*) FROM public.jobs WHERE client_id = 'CLIENT_ID'
UNION ALL
SELECT 'reports (by captured id)', count(*) FROM public.reports WHERE client_id = 'CLIENT_ID'
UNION ALL
SELECT 'storage objects', count(*) FROM storage.objects WHERE bucket_id = 'uploads' AND name LIKE 'CLIENT_ID' || '/%'
UNION ALL
SELECT 'terms_acceptances', count(*) FROM public.terms_acceptances WHERE user_id = 'AUTH_USER_ID';
```

The by-captured-id arms are why step 0 records the IDs: once the clients row is
gone, its children can no longer be found through it — only through the IDs you
wrote down beforehand. (Child tables hang off `jobs`, so a zero `jobs` count with
zero `reports` and zero `narratives` at step-0 parity means the cascade ran; the
`ingested_data`/`scores` rows cannot outlive their `jobs` FK.)

If the requester's email matched an auth user with a *different* clients-row email
(the section-2 mismatch case), run the residue arms once per known email.

## 5. Access and portability (GDPR Art. 15 / 20, CCPA right to know)

Resolve IDs per section 2, then assemble the whole package as one JSON document —
JSON satisfies Art. 20's "structured, commonly used, machine-readable". Omit any
`jsonb_build_object` entry whose ID doesn't exist for this person (e.g. no
`advisor_record` for a plain client).

```sql
WITH ids AS (
  SELECT 'AUTH_USER_ID'::uuid AS user_id,
         'CLIENT_ID'::uuid    AS client_id,
         'ADVISOR_ID'::uuid   AS advisor_id
)
SELECT jsonb_build_object(
  'generated_at', now(),
  'auth_user', (SELECT jsonb_build_object('id', u.id, 'email', u.email, 'created_at', u.created_at, 'last_sign_in_at', u.last_sign_in_at, 'profile', u.raw_user_meta_data) FROM auth.users u, ids WHERE u.id = ids.user_id),
  'linkedin_identity', (SELECT jsonb_agg(jsonb_build_object('provider', i.provider, 'identity_data', i.identity_data, 'created_at', i.created_at, 'last_sign_in_at', i.last_sign_in_at)) FROM auth.identities i, ids WHERE i.user_id = ids.user_id),
  'client_record', (SELECT to_jsonb(c) FROM public.clients c, ids WHERE c.id = ids.client_id),
  'advisor_record', (SELECT to_jsonb(a) FROM public.advisors a, ids WHERE a.id = ids.advisor_id),
  'questionnaire_responses', (SELECT jsonb_agg(to_jsonb(q)) FROM public.questionnaire_responses q, ids WHERE q.client_id = ids.client_id),
  'jobs', (SELECT jsonb_agg(to_jsonb(j) ORDER BY j.created_at) FROM public.jobs j, ids WHERE j.client_id = ids.client_id),
  'ingested_data', (SELECT jsonb_agg(to_jsonb(d)) FROM public.ingested_data d, ids WHERE d.job_id IN (SELECT j.id FROM public.jobs j WHERE j.client_id = ids.client_id)),
  'scores', (SELECT jsonb_agg(to_jsonb(s)) FROM public.scores s, ids WHERE s.job_id IN (SELECT j.id FROM public.jobs j WHERE j.client_id = ids.client_id)),
  'narratives', (SELECT jsonb_agg(to_jsonb(n)) FROM public.narratives n, ids WHERE n.job_id IN (SELECT j.id FROM public.jobs j WHERE j.client_id = ids.client_id)),
  'reports', (SELECT jsonb_agg(to_jsonb(r)) FROM public.reports r, ids WHERE r.client_id = ids.client_id),
  'terms_acceptances', (SELECT jsonb_agg(to_jsonb(ta)) FROM public.terms_acceptances ta, ids WHERE ta.user_id = ids.user_id),
  'waitlist', (SELECT jsonb_agg(to_jsonb(w)) FROM public.waitlist w WHERE lower(w.email) = lower('REQUESTER_EMAIL')),
  'uploaded_files', (SELECT jsonb_agg(jsonb_build_object('path', o.name, 'created_at', o.created_at, 'size_bytes', (o.metadata->>'size')::bigint)) FROM storage.objects o, ids WHERE o.bucket_id = 'uploads' AND o.name LIKE ids.client_id::text || '/%')
) AS dsr_package;
```

Notes that matter when serving this:

- **Raw uploads are part of the answer.** `uploaded_files` lists them; download the
  actual objects from the Storage browser and include the originals in the
  delivery. For pure portability the raw ZIP/XLSX are arguably the whole point —
  the person gave them to us and can take them elsewhere.
- **Size:** `ingested_data` and `scores` carry large JSONB (a real single-report
  account measured ~175 KB and ~95 KB respectively). Deliver as an attached
  `.json` file (zipped if large), never pasted into an email body.
- **Scope discipline:** the query is keyed entirely to the requester's own IDs, so
  it cannot pick up anyone else's rows. For an **advisor**, do not export their
  roster clients' data — those are other data subjects; the advisor's package is
  their advisors row, their own is_self client chain, and their consent records.
- **Deliver only after identity verification** (section 1), to the address on the
  account. A misdirected access package is itself a data breach (§11's notify
  clocks would apply).

## 6. Rectification (Art. 16)

- **Questionnaire answers** — self-service; the portal questionnaire is editable
  and re-submittable by the account holder. No manual work.
- **`display_name` / `email` on the clients row** — no UI for these until
  ORPHEUS-42; a verified request is a manual UPDATE:

  ```sql
  UPDATE public.clients
  SET display_name = 'NEW_VALUE'   -- and/or email = 'NEW_VALUE'
  WHERE id = 'CLIENT_ID'
  RETURNING id, display_name, email;
  ```

- **The auth-account email and LinkedIn profile fields** (name, picture) come from
  LinkedIn OIDC — we don't master them. The person corrects them on LinkedIn and
  they resync at next sign-in. Correcting `clients.email` does not change where
  Supabase auth thinks the person lives; the two are independent (section 2's
  mismatch case is this, benignly).

## 7. Restriction and objection (Art. 18 / 21)

Short section because there is little to restrict or object to:

- **No marketing processing exists** — no ads, no sale/share (§14), no marketing
  emails. An objection to marketing is satisfied by stating that fact.
- **Analytics** (Vercel Web Analytics + Speed Insights, §4.2/§15) is cookieless and
  aggregate with a daily-rotating visitor hash — there is no per-user record to
  restrict or delete. Objection to this legitimate-interest processing is honoured
  by removing the person's data generally (i.e., erasure) rather than by a
  per-user toggle, which cannot exist for data that is not per-user.
- **Practical restriction hold:** while a dispute is open (e.g. contested accuracy,
  Art. 18(1)(a)), set the clients row inactive and don't run new jobs for it:

  ```sql
  UPDATE public.clients SET status = 'inactive' WHERE id = 'CLIENT_ID';
  ```

  That stops all new processing of the person's data while retaining it — which is
  what restriction means. Reverse with `status = 'active'` when resolved.

## 8. The request log (Art. 5(2) accountability)

Keep the log **out of the repo** — a list of who exercised privacy rights is
itself personal data and doesn't belong in git history. It lives in the Shared
Canon Drive folder (`06_Operations`) as **"DSR Log"**; create it from this template
on first use if it doesn't exist yet. One row per request:

| Field | Content |
|---|---|
| Received | Date + channel (email, in-product) |
| Requester | Name / email as given |
| Verified | How identity was verified, and when |
| Right invoked | Erasure / access / portability / rectification / restriction / objection |
| Jurisdiction claimed | GDPR / UK / CCPA / other / none stated |
| Deadline | Computed from Received per the section-1 table |
| Actions | What was done, by whom — cite the runbook sections/queries run and the verification result |
| Completed | Date the response went out |
| Notes | Refusals (with legal basis, Tim's sign-off), extensions invoked, oddities |

Log **every** request — including "no data held" responses, self-service deletions
we merely pointed someone to, and refusals. The log is the evidence that we honour
the policy; an empty log column is what a regulator reads as "didn't happen".

---

## Testing evidence (2026-08-11)

Per the ticket's note that a first live use must not be the first execution, every
query above ran against production on 2026-08-11 via the Supabase MCP:

- **Resolution query** — run for a real account; correctly returned its auth user,
  advisors row, and clients row, the latter matched **via `user_id` despite a
  different clients-row email** — the mismatch case is real in prod today.
- **Access/portability package** — assembled complete for the same account: all 14
  keys populated as expected (7 jobs with matching ingested_data/scores/reports,
  35 narratives, 1 terms acceptance, 14 storage objects; waitlist correctly null).
- **Orphan catcher** — a scratch clients row with `user_id IS NULL` and a
  synthetic email was inserted, the section-4 query **caught it in the
  orphaned_clients arm**, the row was deleted, and the re-run came back all-zero.
- **Advisor-roster guard** — run for a real advisor; returned 11 non-self roster
  clients, i.e. correctly blocking (matches the live 409 behavior verified during
  ORPHEUS-124's validation).

Related tickets: ORPHEUS-124 (self-service deletion — the executable twin of
section 3), ORPHEUS-125 (published policy this runbook operationalizes),
ORPHEUS-126 (consent records swept by the auth-user cascade), ORPHEUS-42 (will
retire section 6's manual UPDATE).
