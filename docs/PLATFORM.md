# Frameport routed platform, 0.2

## The deployment correction

The old Vercel entrypoint created the local worker application in `/tmp`. That made the homepage accessible but did not provide durable projects or a suitable conversion service. It also returned an unjustified `worker: available` response. That entrypoint is removed.

Vercel now runs `frameport.gateway.create_gateway`. It serves the real routed application and forwards API requests to one operator-configured HTTPS origin. It creates no database, signing key, session store or queue on ephemeral Vercel disk. With no upstream it returns `canConvert: false`, rejects job submissions with 503 and exposes an explicit connection state at `/settings`. It never pretends a recorded sample is a working cloud conversion.

## Application routes

`/` retains the approved monochrome landing and live shader. `/convert` contains the conversion form without the landing hero. `/projects` is the private project library. Every project has `/projects/{id}/review`, `/content`, `/source`, `/verify` and `/export`. `/settings`, `/login` and `/docs` are dedicated routes.

Direct links and refreshes work because both gateway and persistent service explicitly serve these document routes. Unknown API/static routes return errors, never the app shell. Source file, output format, selected page and width are URL state. Back/forward navigation restores them. Responses from older requests cannot overwrite a newer project or file selection.

The library supports searching/filtering and project renaming/deletion. Editing uses an expected revision to reject stale saves from another tab. All changes pass through the real API. Sharing a project link does not grant access.

## Private workspace authentication

An operator sets a random `FRAMEPORT_API_KEY` on the persistent service. The browser exchanges it for an opaque HTTP-only, SameSite=Strict session, with Secure enabled for the configured HTTPS public origin. Only a hash is stored on disk. Sessions survive process restarts, expire after seven days, are revoked at logout and become invalid when the operator rotates the access key. The key is not retained in browser storage. The gateway forwards the caller's cookie, not a privileged service credential.

Login attempts are bounded in the database. Writes require JSON and validate Origin against the worker host or the explicitly configured public website origin. This release has one authenticated owner workspace, not public signup, independent tenants or billing.

## Persistent execution

A long-running service owns `/data`, its SQLite WAL database, sessions, capture files, revision summaries, evidence and exports. The SQL queue is the source of truth. Submissions and retries are committed before responding. Idempotency keys avoid accidental duplicate jobs. Queue claiming and edit revisions are transactional.

One supervisor owns the volume lock. Each conversion runs in a new OS process, with API/cloud credentials stripped from its environment, and a separately launched Chromium. Cancellation and deadline expiry terminate its process group. Graceful service shutdown preserves queued work; interrupted execution is retried once before an explicit failure. A browser preflight must pass before readiness becomes true. Multiple service replicas sharing the volume are not supported.

Revision history records previous measurements; it does not claim to retain every historical ZIP. Current downloads require a completed revision. Five-minute signed download links bind the project, revision and format. Through the gateway, large ZIP downloads go directly to the persistent origin rather than buffering the whole archive through a Vercel function. Signed HTML previews retain their restrictive sandbox and CSP.

## Deploy the persistent worker

Railway connection is still required before this service can be provisioned through ChatGPT. The repository includes `railway.json`, the Dockerfile and `deploy/start-worker.sh`. Provision one service from this repository, mount a durable volume at `/data`, and configure:

- `FRAMEPORT_API_KEY`: a private random value of at least 24 characters.
- `FRAMEPORT_PUBLIC_ORIGIN`: `https://frameport.vercel.app`.
- `FRAMEPORT_DATA`: `/data`.

Create its HTTPS domain. `RAILWAY_PUBLIC_DOMAIN` is used for the worker's allowed Host headers. The start script initialises root-owned volume permissions, then drops to `pwuser`. It refuses the unsandboxed test flag. The `/api/ready` check must pass with actual Chromium sandbox support; the script does not weaken the sandbox to make deployment green. If the provider cannot support the required isolation, use a suitable sandbox-capable host instead.

On Vercel, set `FRAMEPORT_WORKER_ORIGIN` to that HTTPS origin and redeploy. No API key belongs in the frontend or Vercel gateway configuration. Sign in through the website with the private worker access key. Enable volume backups and verify restore behaviour before relying on retained projects.

The image and configuration are prepared, not evidence of a running Railway service. Production connection must be verified with a real hosted conversion after provisioning.

## Verification

`pytest -q` covers sessions, persistence, atomic queue operations, competing edits, gateway isolation, fail-closed readiness, direct document routes, signed downloads and process termination, alongside the earlier compiler/security cases. `node --test tests/router.test.mjs` checks canonical routing and URL input validation.

`scripts/check_platform.py` starts the actual gateway and worker as HTTP services and converts only the authored Forma fixture. It tests login/refresh, an actual queued subprocess conversion, project renaming, source deep links, back navigation, edits, revision conflicts/history, direct signed downloads, responsive screens and logout. It does not substitute an offline renderer or pre-completed job.

The prior HTML/React build, shader and presentation suites remain in CI. After they pass, CI synchronises only the verified compiled studio files into Git, with a fast-forward check to avoid overwriting concurrent work. Vercel and Docker also compile TypeScript during their build.

## Remaining production boundaries

This is a real single-workspace application, not a completed public multi-tenant service. External live Framer compatibility, provider sandbox support, network-level egress enforcement, backup/restore, operational monitoring and unauthorised-use controls require their own verification. A green authored-fixture workflow does not establish universal Framer fidelity.

Official platform references reviewed for this implementation:
- https://vercel.com/docs/routing/rewrites
- https://vercel.com/docs/project-configuration/vercel-json
- https://docs.railway.com/volumes
- https://docs.railway.com/config-as-code/reference
- https://playwright.dev/python/docs/docker
