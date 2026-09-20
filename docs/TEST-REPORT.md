# Verification report

**20 September 2026 | Tested code 8418f820c78bfa600ee73d516678145cd342c2b9**

## Current result

[GitHub Actions run 35531590101](https://github.com/EmotiveImpact/frameport/actions/runs/35531590101), check job `106133040098`, completed successfully, followed by the success-only compiled-studio synchronisation job.

| Check | Measured result |
|---|---|
| Python unit, API and security tests | 125 passed |
| URL router tests | 17 passed |
| New gateway, session, durable queue and subprocess platform journey | 40 passed |
| Retained browser editing/export acceptance | 44 passed |
| Original WebGL shader/design suite | 46 passed |
| Typography and presentation suite | 77 passed |
| HTML/source comparison | 10 passed |
| HTML render/disclosure checks | 17 passed |
| Independent built-React/source comparison | 10 passed |
| Generated React dependency install, strict check and production build | Passed |
| Generated dependency audit | Zero reported vulnerabilities at the recorded run |

The current artefact is `10611139479`, SHA-256 `7d0fcc7a3c658d12400bae2888afb3de69d3d6649d51f0ecaa44bb1259c5a92b`. The downloaded archive digest was checked before inspection. See `evidence/platform-ci.json` for machine-readable provenance.

## What the new journey demonstrates

An unseeded private workspace is opened through a real HTTP gateway. The test signs in and refreshes, confirms that another browser context remains unauthenticated, then creates the original Forma conversion. The durable queue claims it and an actual subprocess runs the capture/compiler/verification pipeline.

The browser then reopens source by URL, refreshes, uses back navigation, renames the project, changes text, waits for regeneration, rejects a stale editor revision, reads saved revision history and downloads both actual ZIP archives. Their content contains the edit. The test checks responsive screens and logout, then confirms the project remains on disk after both servers stop. All 40 checks passed and no uncaught browser errors were recorded.

The pooled gateway client previously retained upstream cookies. A new regression demonstrated that an unauthenticated visitor could inherit that state. The fix uses explicit per-request headers plus a rejecting cookie policy. The unit case and real independent-context checks pass after the correction. No production worker had been connected during this development stage.

## Scope, not a universal guarantee

The source is the original two-page Forma fixture, not a Framer-published website. CI's trusted authored-site tests use the explicitly marked unsandboxed test flag; they do not verify a production host's browser sandbox. The hosted start script refuses that flag.

Vercel serves the new application and gateway. At the recorded check it has no configured persistent worker and therefore reports `canConvert: false`. A successful CI run is not a completed Railway deployment. The public worker, volume, provider sandbox and hosted conversion still require provisioning and verification.

The production conversion report verifies HTML states. The separate CI pipeline builds and compares the sample's React output. It must not be interpreted as automatic React build verification for every job. Likewise, schema/queue persistence tests are not a backup/restore assurance or multi-tenant isolation review.

Historical offline and earlier design reports remain under `docs/evidence`. Their names and original scope are preserved. `platform-ci.json` and this report describe the current platform result.
