# Frameport
### Your design. Your code. Your rules.

A local conversion studio that reconstructs published websites as editable React + TypeScript and standalone HTML/CSS. The source is on `main` in `EmotiveImpact/frameport`. **Version 0.1.0 is a single-workspace developer release, not a universally verified Framer converter or hosted SaaS.**

## Current verified build

Code commit `bf340ab3f8a8ee27c45fd7ec9ac58e385c844b1c` passed [GitHub Actions run 35504470191](https://github.com/EmotiveImpact/frameport/actions/runs/35504470191) on 20 September 2026: 75 unit/API cases, 10 HTML comparisons, 10 built-React comparisons, 17 HTML render/disclosure checks and 44 browser acceptance checks. The generated dependency audit reported zero vulnerabilities at that run. See [the test report](docs/TEST-REPORT.md) for scope and provenance.

These results use our original two-page Forma fixture through real HTTP navigation. **They do not establish compatibility with a genuinely Framer-published site.** The earlier offline evidence remains separately labelled in `docs/evidence`.

## Start locally

Requires Python 3.11+ and internet access for dependency/browser installation. The compiled studio is included, so Node is not required to start the converter.

```bash
cd frameport
bash scripts/start.sh
```

Open **http://127.0.0.1:8040**. On Windows, run `powershell -File scripts/start.ps1`. Manual setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m playwright install chromium
python -m frameport.cli
```

Linux may additionally need `python -m playwright install --with-deps chromium`. Chromium's sandbox must work for untrusted captures. Do not disable it to capture public sites. The unsandboxed test switch is exclusively for controlled, authored fixtures.

Select **Convert the sample site** for the complete local workflow. For your own published site, paste its URL, confirm permission, choose page coverage and submit. Inspect the result before publishing.

## What you can do

Watch conversion progress, switch pages and widths, compare source/export/difference images, interact with the sandboxed HTML preview, browse real generated source, edit extracted text and rebuild both exports. The editor refreshes to the saved revision. Cancellation, retries, persistence and ZIP/report downloads are implemented.

React exports contain components, pages, `src/content/site.json`, local styles/assets, route entries and Vite configuration. In that exported folder run `npm install`, `npm run dev`, then `npm run build` before deployment. Host the resulting site at the domain root. HTML exports can be served with `python -m http.server 8080`.

Every export includes its conversion report and asset manifest. Original source scripts and the Framer runtime are not shipped. A Frameport-owned adapter handles explicit disclosures and prevents form submission until you connect a backend. There is no screenshot-as-layout export, HTML-string React wrapper or required AI API key.

The optional project-manifest importer archives project/CMS context. Its experimental read-only Framer plugin adapter is not editor-verified and does not compile the original canvas or automatically bind CMS routes.

## Evidence boundaries

The production conversion pipeline verifies HTML, not every generated React build. CI separately installs, builds and measures the specific fixture's React output. A per-job `reactBuild: not-run` report remains accurate unless that particular output is separately tested; the fixture's green CI must not be applied to arbitrary exports.

Capture currently uses desktop DOM with original responsive CSS. Breakpoint-specific DOM changes, arbitrary scripts, advanced motion, custom code, canvas/WebGL, embedded frames, authentication and backend migration remain outside demonstrated coverage. Original Framer abstractions are not recovered.

Visual evidence covers 390, 540, 768, 1024 and 1440px, reduced motion and up to 6,000px down each page. Comparisons require equal dimensions and allow at most 2% changed pixels, using a 22-level RGB-channel tolerance. This is not a general conversion-success percentage.

## Configuration and safety

See `.env.example`; variables must be exported in the shell because the app does not automatically load `.env`. Workspace data and preview keys live in `.frameport/`. Do not commit or share this directory. Retention cleanup runs at startup. Remote binding requires a private access key of at least 24 characters and configured allowed hosts. One key opens one shared workspace, not separate tenants.

Capture defaults to three pages, maximum eight, with limits of 7,000 nodes/page, 80 levels, 300 assets, 12 MB/resource, 120 MB transfer, 1,200 fetches, 240 seconds/job and 12 pending jobs. Rebuilding revokes access to old exports and revision-scoped previews until completion. Signed previews expire after 30 minutes. The iframe has no same-origin privilege or form submission.

Docker/Compose configuration is included but has not been executed in this delivery. Public hosting still requires isolated browser workers, enforced network egress, tenant identity/storage isolation, quotas, operational monitoring and security review. Read [SECURITY.md](docs/SECURITY.md). No hosted conversion service has been deployed.

## Development

```bash
npm ci --ignore-scripts
npm run build
npm run typecheck
pytest -q
python -m scripts.check_fixture --data .frameport-check --output fixture-result.json
```

After installing and building the resulting fixture's React project, run:

```bash
python -m scripts.check_acceptance --job fixture-result.json --data .frameport-check --output artifacts/acceptance
```

This acceptance runner refuses offline reference evidence and tests actual HTTP, authentication, preview isolation, source browsing, content regeneration and browser ZIP downloads. CI uses the unsandboxed browser switch only for the trusted authored fixture, not as a production isolation assurance.

The root npm lockfile was recovered from an actual successful CI install. Export lockfiles are produced by real installs. `scripts/check_fixture --offline`, `check_editing` and `check_preview` are explicitly limited test harnesses; they are not substitutes for normal navigation. `scripts/make_preview` packages existing results into a portable, read-only studio preview, not a live conversion service.

See [STATUS.md](STATUS.md), [ROADMAP.md](ROADMAP.md) and [ARCHITECTURE.md](docs/ARCHITECTURE.md). The next external acceptance target is an authorised, genuinely Framer-published marketing site.
