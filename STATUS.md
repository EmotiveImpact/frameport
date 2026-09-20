# Frameport status

**20 September 2026 | Routed private workspace and persistent conversion backend**

## Actual delivery state

The new web application and stateless gateway are deployed at https://frameport.vercel.app. `/convert`, `/projects` and `/settings` respond successfully, and the new compiled router is served. The tested code deployment is Vercel `dpl_AUEjpEKj88c34VUU5KgY1DkFJqip`, state READY, from commit `8418f820c78bfa600ee73d516678145cd342c2b9`.

**Hosted conversions are not active yet.** Railway is not connected, so no persistent worker or volume has been provisioned. The live gateway correctly reports `worker: unconfigured`, `storage: not-connected`, `canConvert: false`. It rejects conversion submissions rather than accepting jobs into temporary Vercel storage. The remaining deployment step is to connect Railway, provision the worker/volume, verify its sandboxed readiness, and configure `FRAMEPORT_WORKER_ORIGIN` on Vercel.

## Implemented platform

Dedicated document routes for conversion, projects, review, content, source, verification, exports, settings, login and documentation. Direct links, refresh and browser back/forward restore the selected project/source view. Project search/filtering, rename and deletion use the actual API. The approved pure-black design, heavier typography and live monochrome WebGL shader remain intact.

Private sign-in uses an opaque HTTP-only session, stored as a hash on the persistent service. Sessions survive restarts, expire, and are revoked on logout or access-key rotation. The gateway forwards only the current visitor's credentials and does not share upstream cookies between visitors. A failing-before-fix unit regression and independent browser-context checks verify that boundary.

Projects, revision summaries and queue entries are stored on the worker's durable disk. Each conversion runs in a supervised subprocess. Cancellation and timeouts terminate its process group. Queue claims and revision-checked edits are transactional, accidental duplicate submissions are idempotent, and interrupted work is retried once. Five-minute download links are bound to a completed project revision and export format.

This is one authenticated owner workspace, not public signup, billing or multi-tenant isolation. Separate processes are operational isolation, not a substitute for hardened per-tenant containers or network-level egress enforcement.

## Verified code and evidence

[GitHub Actions run 35531590101](https://github.com/EmotiveImpact/frameport/actions/runs/35531590101), check job `106133040098`, passed for commit `8418f820c78bfa600ee73d516678145cd342c2b9`. The compiled studio synchronisation job also passed; compiled source is committed on main. Any subsequent documentation-only update does not change the tested application code.

Measured results: **125 Python tests, 17 router tests, 40 new platform checks, 44 retained browser acceptance checks, 46 shader/design checks, 77 typography/presentation checks, 10 HTML comparisons, 17 HTML render/disclosure checks and 10 built-React comparisons passed.** The generated React installation/production build passed. The dependency audit reported zero vulnerabilities at that run. The platform report recorded no uncaught browser errors.

The new platform test starts an actual HTTP gateway and persistent service with an empty workspace. It signs in, refreshes, queues and completes the original Forma conversion in a subprocess, reopens source deep links, renames the project, saves edits, rejects a stale revision, downloads both archives and verifies persistence after the services stop. No offline document adapter or pre-completed project is substituted.

Downloaded artefact `10611139479` was verified against SHA-256 `7d0fcc7a3c658d12400bae2888afb3de69d3d6649d51f0ecaa44bb1259c5a92b`. Its project-library, review, export and mobile screenshots were inspected. Full provenance is in `docs/evidence/platform-ci.json`.

## Remaining verification

The successful browser tests run the original authored Forma fixture in CI, not an operational Railway deployment or a genuinely Framer-published source. Provider sandbox support, hosted end-to-end conversion, backup/restore, Framer editor integration and advanced Framer behaviour coverage remain separate acceptance gates. Per-conversion reports do not automatically verify every generated React build.

See `docs/PLATFORM.md` for configuration, security boundaries and the exact remaining deployment steps. Local use remains available through `bash scripts/start.sh`.
