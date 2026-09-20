# Verification report

**20 September 2026 | Current verified code: bf340ab3f8a8ee27c45fd7ec9ac58e385c844b1c**

## Actual GitHub run

[Run 35504470191](https://github.com/EmotiveImpact/frameport/actions/runs/35504470191), job `106061831360`, completed successfully. Its downloaded `fixture-evidence` archive, artefact `10603592232`, was verified against SHA-256 `766440990244d14dec5590db8ceb3db541aaa64ebff8a4dcd525ab68d1a2c2ad`.

| Check | Observed result |
|---|---|
| Unit/API/security-contract suite | 75 passed |
| Studio build and strict TypeScript | Passed |
| Real HTTP Forma capture and HTML comparison | 10 of 10 passed |
| HTML render/disclosure checks | 17 passed |
| Generated React dependency installation, strict check and Vite production build | Passed |
| Built React versus original source, five widths on two pages | 10 of 10 passed |
| Authenticated studio and real-browser acceptance | 44 passed |
| Uncaught browser errors in acceptance | 0 |
| Generated React dependency audit | 0 reported vulnerabilities |

The source fixture produced two pages, nine editable React components, 74 non-empty text fields and one local SVG asset. Both initial HTML and built-React comparisons recorded zero changed pixels under the stated channel tolerance. This is evidence for this authored fixture, not a percentage guarantee for arbitrary websites.

## Browser journey actually exercised

The runner uses actual HTTP navigation and rejects the earlier offline-document references. It opens installed React production output, checks local images and mobile disclosures, authenticates against a real Uvicorn/FastAPI worker, opens the sandboxed iframe and confirms it cannot access the parent document or service-worker API.

It checks the response CSP, reads generated source, edits a field through the studio, waits for the real worker to regenerate it, confirms the editor and source viewer refresh, checks changed visual evidence and revoked old tickets, then downloads and opens both HTML and React ZIPs to verify the saved content. All 44 assertions passed. The intentionally changed heading is expected to differ from the original source; that does not represent a broken regeneration.

## Corrections made during verification

Numeric textarea dimensions fixed the first strict React build failure. The source-view assertion now waits for the asynchronous fetch. Playwright's test-only service-worker injection was removed from the trusted studio test context because it accessed an unavailable API in opaque sandboxed frames; production capture blocking, iframe isolation and CSP remain intact and are explicitly tested.

Inspection of an initially green run's screenshot revealed stale text in the editor after rebuilding. The client now clears its old content/source caches and reloads the finished revision. Two additional browser assertions verify that correction. Vite 6.4.3, a genuine root lockfile and a generated-dependency audit were also added.

## Limits and historical evidence

The live source is the original Forma fixture, **not a Framer-published site**. CI intentionally runs its trusted authored fixtures without the Chromium sandbox; it does not establish production isolation or public-service readiness. The editor plugin, Docker and arbitrary Framer interactions remain outside this evidence.

The production pipeline's per-conversion report verifies HTML only. The additional React production build and comparisons are performed separately by CI for this specific output. The report is not changed to claim automatic React verification for every job.

Earlier `fixture-report.json`, `editing-checks.json`, `react-syntax.json`, `ui-checks.json` and `unit-tests.txt` in `docs/evidence` record the initial, explicitly labelled offline delivery. They are historical, not the latest CI result. `ci-summary.json` links the current measured result to its commit, run and archive digest. The archive retains full current reports, comparisons, source model, genuine lockfiles, screenshots and output ZIPs; private workspace keys and databases are excluded.
