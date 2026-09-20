# Verification report

**Date:** 20 September 2026. **Release:** 0.1.0. **Result:** functional developer release with explicitly unverified external integrations.

## Measured results

| Check | Observed result | Scope |
|---|---|---|
| Unit/API/security suite | 65 passed | URL/IP policies, mixed DNS answers, redirect checks, local asset fetch, SVG sanitisation, escaping, numeric JSX attributes, storage, path containment, host/auth/CSRF/body/queue limits, cancellation and unfinished-export protection |
| Original fixture conversion | 2 pages, 9 React components, 1 local SVG asset | Authored Forma fixture; real extraction, compiler, local asset fetching and ZIP packaging |
| HTML visual comparison | 10 of 10 passed | Two pages at 390, 540, 768, 1024 and 1440px; actual document-height screenshots, not just the first viewport |
| Render/disclosure checks | 17 passed | 10 image/render checks, 6 native-details checks and 1 visible mobile aria-controls disclosure |
| Content editing and API lifecycle | 14 passed | Real API calls, completed ZIP access, signed preview access, revision invalidation, regenerated React JSON, escaped HTML, new ZIPs and bad field rejection |
| Intentional edit detection | 5 comparisons flagged differences | A changed home-page heading deliberately caused visual review, while the unchanged page remained a reference |
| Studio UI | 20 passed; 0 JavaScript errors | Overview, conversion preview, source, content and report views at four viewport sizes |
| Studio TypeScript | Passed | Strict compile of the actual studio source |
| Bridge adapter TypeScript | Passed | Read-only adapter interface and implementation, not the Framer SDK/editor integration |
| Generated source syntax | 15 files checked; 0 syntactic errors | React/TypeScript/JavaScript parsing/transpilation, **not** dependency resolution or a production build |

The matched-pixel figure in the fixture report is measured from actual rendered images. It is not a conversion-success percentage for arbitrary websites. PNG dimensions are checked against the declared capture dimensions. The report files preserve each comparison, height, changed-pixel count, tolerance, issue and execution mode.

## Environment limitations and substitutions

Chromium navigation is blocked in the authoring environment by administrator URL policy. That policy was left in place. A test-only adapter rendered existing authorised local fixture files and generated output with `set_content`, inlining their local resources. It restored source URL/style context for the extractor and labelled every resulting report `offline-document-harness`. No blocked public website was accessed through this mechanism.

Therefore these results **do not verify normal browser navigation, live Framer hydration, Framer animation equivalence, real iframe resource loading under response CSP, or browser downloads**. API preview/ZIP responses were exercised independently with real application requests. The portable UI was tested with its actual embedded fixture data, not a live HTTP backend connection. It is not presented as a hosted converter.

The network in this environment also prevented fresh npm dependency installation. Generated React syntax was checked with an installed TypeScript compiler, but **npm install, full module/type resolution, Vite production build and actual modern React rendering remain unverified**. No lockfile or successful build output was invented. The Docker image and GitHub Actions workflow were written, not executed. The Framer adapter was checked against its local interface, not an installed SDK or genuine editor session.

## Evidence files

`evidence/fixture-report.json`, `evidence/editing-checks.json`, `evidence/react-syntax.json` and `evidence/ui-checks.json` contain actual results. The supplied visual-evidence ZIP contains the matching source/export/difference PNGs and UI screenshots. The two sample export ZIPs contain the real generated code and conversion report.

## Reproduction

Run the README's development commands. `scripts/check_fixture.py` defaults to normal browser navigation; use `--offline` only for an explicit restricted-environment test. Its authored fixture is not a secretly substituted Framer website. CI is configured to attempt a normal local-fixture capture and fresh React production build when the repository is uploaded. Until that actually runs, CI is **unverified**, not green.
