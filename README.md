# Frameport
### Your design. Your code. Your rules.

Frameport reconstructs an authorised published website as editable React/TypeScript and HTML/CSS. The approved black studio, heavier typography and original WebGL shader are preserved.

**The application now has real routes, persistent sessions, a durable project queue and a separately running browser worker.** The Vercel application is deployed at https://frameport.vercel.app. **Hosted conversions are not active until the persistent worker is provisioned and connected.** The interface explicitly reports this missing connection rather than inventing an available worker or temporary projects.

## Start here

- `/convert`: begin a new conversion without the landing hero.
- `/projects`: your private project library, with search, filters, rename and delete.
- `/projects/{id}/review`, `/content`, `/source`, `/verify`, `/export`: the project's actual working screens.
- `/settings`: real worker, storage and access status.
- `/login`: sign in to the private workspace.

Refreshes and direct links restore the project and selected source file. Browser back/forward works. Text edits are revision-checked so an old tab cannot overwrite a newer save. React and HTML downloads contain actual editable files, not an embedded Framer site.

## Deployment architecture

Vercel runs the web application and a stateless API gateway. It does not create SQLite databases, browser processes or project files in temporary serverless storage.

The persistent service owns one durable volume containing projects, session hashes, the SQL job queue, captured assets, reports and exports. Its supervisor launches each conversion in a separate process, enforces deadlines/cancellation and recovers interrupted queue entries. Chromium must pass its readiness check before conversions are accepted.

This is an authenticated **single-owner workspace**, not a public multi-tenant SaaS. Sign-in exchanges the private worker access key for an HTTP-only session. The gateway does not store or reuse an owner's cookie for another visitor. Public signup, billing and independently isolated tenants are not implemented.

## Run locally

Requires Python 3.11+ and internet access for installation. Compiled frontend files are included; Node is only needed to change frontend code.

```bash
bash scripts/start.sh
```

Open http://127.0.0.1:8040. Windows: `powershell -File scripts/start.ps1`. The original Forma sample exercises the full local flow. Linux may require `python -m playwright install --with-deps chromium`.

Do not disable Chromium's sandbox for untrusted websites. The unsandboxed test switch is reserved for the original controlled fixture, not a solution to a production hosting problem.

## Connect the hosted worker

Railway access is the outstanding deployment dependency. The repository includes `railway.json`, a multi-stage `Dockerfile` and `deploy/start-worker.sh`.

Provision one worker service, mount a persistent volume at `/data`, configure a random `FRAMEPORT_API_KEY` of at least 24 characters and set `FRAMEPORT_PUBLIC_ORIGIN=https://frameport.vercel.app`. The start script drops to a non-root user and refuses the unsandboxed test flag. Its `/api/ready` endpoint must return success with the real browser sandbox enabled.

Set the Vercel variable `FRAMEPORT_WORKER_ORIGIN` to the service's HTTPS origin and redeploy. No private worker key belongs in frontend files or the gateway configuration. Enable and test volume backups before relying on retained projects. See [the platform guide](docs/PLATFORM.md).

The hosted worker and volume have **not** been provisioned merely because these configuration files exist. If a host cannot run Chromium with suitable isolation, use an appropriate sandbox-capable host rather than weakening the checks.

## Development and verification

```bash
npm ci --ignore-scripts
npm run build
npm run typecheck
pytest -q
node --test tests/router.test.mjs
python -m scripts.check_platform --output artifacts/platform
```

The last command exercises actual HTTP gateway requests, session sign-in, an unseeded sample conversion through the durable queue/subprocess, project routes, editing, persistence and browser downloads. It does not use an offline document substitute. CI also retains the independent generated-React production build, HTML/React visual comparisons, shader checks and typography checks. See [STATUS.md](STATUS.md) for the exact tested commit and measured result.

CI commits compiled studio assets only after acceptance passes, and refuses to overwrite a newer main branch. Vercel and Docker also compile the TypeScript during deployment.

## Conversion limits

The original authored fixture is tested; a genuinely Framer-published site remains a separate acceptance target. Desktop DOM reconstruction, preserved responsive CSS and selected native/disclosure behaviours are implemented. Arbitrary Framer motion, changing DOM variants, custom components, embedded canvases and backend migration are not universally reconstructed. Forms require their own submission service.

Per-conversion reports verify captured HTML states, not automatically every React production build. The separate CI suite builds the particular sample's React output. Read the report before publishing. See [SECURITY.md](docs/SECURITY.md), [PLATFORM.md](docs/PLATFORM.md) and [ROADMAP.md](ROADMAP.md).
