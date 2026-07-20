-- 019_uploads_bucket_config.sql  (ORPHEUS-109)
--
-- Pins the `uploads` Storage bucket configuration in source. The bucket
-- itself was created via the dashboard for ORPHEUS-108 (browser-direct
-- upload), and its config has since been edited live twice: the 50 MB
-- file_size_limit, and the 2026-07-20 hotfix adding
-- `application/x-zip-compressed` to the MIME allowlist after every Windows
-- client's ZIP upload 400'd with InvalidMimeType (Windows registers .zip
-- as x-zip-compressed, and Storage honors the OS-reported type on the
-- uploadToSignedUrl path). Dashboard-only state is how that hotfix would
-- get silently lost on a project rebuild — same posture as ORPHEUS-43's
-- move of the Railway build config into source.
--
-- Values below were captured verbatim from live prod (2026-07-20,
-- post-hotfix). Notes:
--   - x-zip-compressed stays in the allowlist even though the client now
--     normalizes MIME before upload (ORPHEUS-109) — defense-in-depth for
--     deploy skew and any non-normalizing caller.
--   - application/octet-stream is allowed because some browsers report
--     archives with no specific type.
--   - The 50 MB cap coexists awkwardly with the frontend's 150 MB
--     advisory and the server-side 200 MB cap; reconciling the three is
--     ORPHEUS-111, not this migration. This just records reality.
--
-- Idempotent: safe to re-run, and recreates the bucket with the correct
-- config on a fresh project.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'uploads',
    'uploads',
    false,
    52428800,  -- 50 MB
    array[
        'application/zip',
        'application/x-zip-compressed',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/octet-stream'
    ]
)
on conflict (id) do update set
    public             = excluded.public,
    file_size_limit    = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;
