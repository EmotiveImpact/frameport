# Frameport
### Your design. Your code. Your rules.

An evidence-led conversion studio that reconstructs published websites as editable React + TypeScript and standalone HTML/CSS. Built for a single trusted workspace. **Version 0.1.0 is a developer release, not a universally verified Framer converter or public SaaS.**

The actual code captures DOM and styles through Chromium, collects local assets, generates separate components and content files, compares rendered HTML at five widths, and packages real ZIP exports. The studio provides source browsing, image comparison, page/device switching, content editing, regeneration, progress, cancellation, retry and verification reports. There is no AI API key, screenshot-as-layout export, original script bundling or `dangerouslySetInnerHTML` wrapper.

## Start locally

Requires Python 3.11+ and internet access for the initial dependency/browser installation and published-site capture. The compiled studio is already included, so Node is not required to start the converter.

```bash
cd frameport
bash scripts/start.sh
```

Then open **http://127.0.0.1:8040**. On Windows, run `powershell -File scripts/start.ps1` from the project folder. A manual installation is:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m playwright install chromium
python -m frameport.cli
```

On Linux, Playwright may require system dependencies: `python -m playwright install --with-deps chromium`. Chromium must be able to initialise its sandbox for untrusted captures. Do not solve sandbox errors by disabling it for public sites. The `FRAMEPORT_UNSANDBOXED_TEST_BROWSER` switch is exclusively for trusted authored test fixtures.

First try **Convert the sample site**. This uses our original two-page Forma fixture, not a hidden live Framer benchmark. To convert an authorised published site, paste its address, select the page limit, confirm permission and submit. Review the report before publishing either output.

## What you get

React projects contain `src/components/*.tsx`, `src/pages/*.tsx`, `src/content/site.json`, local styles/assets, page entries, a Vite configuration and a package manifest. Edit text, layout and code independently. In the exported React folder run `npm install`, `npm run dev`, then **`npm run build`** before deployment. React export assumes domain-root hosting.

HTML projects contain actual page markup, local styles/assets, and a small Frameport-owned disclosure/form-safety adapter. Serve the exported directory with `python -m http.server 8080`. There is no Framer runtime dependency in generated application code. CSS and asset warnings still require review.

Each ZIP includes `conversion-report.json` and `asset-manifest.json`. Project manifests, when supplied, are archived with optional CMS JSON. A bridge manifest adds reference context; it does not compile the original Framer canvas or automatically bind CMS records into pages.

The website UI itself is dependency-free TypeScript. The browser worker is Python/FastAPI/Playwright. The generated website target is React/TypeScript or HTML. This separation keeps the studio runnable without a JavaScript dependency install.

## Verification actually performed

See **[docs/TEST-REPORT.md](docs/TEST-REPORT.md)** and its machine-readable evidence. The delivered fixture output was produced through the real extraction/compiler/asset/packaging pipeline, but a clearly labelled offline-document test adapter replaced browser HTTP navigation because the build environment's administrator blocks it. Those restrictions were left intact.

**Not verified here:** a live Framer-published website, a fresh dependency installation and production build of generated React, the plugin inside Framer, Docker startup, or end-to-end browser-to-live-API navigation. A syntactic React check is not a production build. The original source and exported HTML were genuinely rendered and compared; no percentage was invented.

The standalone `Frameport-Studio-Preview.html` supplied alongside this repository embeds the actual fixture evidence and source. It is an interactive, read-only preview, **not a live server**. Website conversion and saving edits require the worker above.

## Scope and boundaries

Initial capture is desktop DOM with preserved responsive CSS. Dynamic DOM variants, arbitrary code overrides, advanced animation, WebGL/canvas, embedded frames, authentication, complex media, non-standard styles and unusual interactions are not automatically reconstructed. Forms are deliberately disabled until a backend is connected. Source scripts are never shipped. Original Framer component abstractions are not recovered.

The visual result measures only generated **HTML**, captured states, five widths (390, 540, 768, 1024 and 1440), reduced motion and at most the first 6,000 pixels of each page. A pixel passes the tolerance when every RGB channel differs by at most 22; a comparison allows at most 2% changed pixels and requires matching dimensions. This is not a global functional-equivalence score. Native details and visible aria-controls buttons receive limited interaction checks, not full animation/state comparisons.

Capture defaults to three pages, maximum eight, 7,000 nodes per page, 80 levels, 300 downloaded assets, 12 MB per response, 120 MB transfer budget, 1,200 fetches, a 240-second job limit and 12 pending jobs. Edits invalidate old reports, ZIP access and signed preview URLs until the new revision completes. Failed jobs never expose a completed download.

## Configuration and data

Environment variables are described in `.env.example`. The application does **not** automatically load `.env`; export variables in your shell, or use Compose's environment support. Jobs, source models, copied assets, evidence, exports, SQLite records and the preview signing key live in `.frameport/` by default. Do not commit that directory. It may contain confidential project content. Retention cleanup runs at startup; old conversions can also be deleted through the API. There is no cloud telemetry.

Default binding is loopback. Remote binding requires an access key of at least 24 characters. The studio keeps that key in memory, not local storage. All authenticated users of one worker share its workspace. This is not tenant isolation. Signed preview URLs expire after 30 minutes and are scoped to a conversion revision. Rendered HTML uses a restricted iframe/CSP with no same-origin privilege or form submission.

## Docker development configuration

A Dockerfile and Compose configuration are included but **not executed in this delivery environment**. Generate a private key, then:

```bash
export FRAMEPORT_API_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose up --build
```

Keep that key private and enter it in the studio. Ports are bound to local loopback. Host support for Chromium's sandbox/user namespaces must be checked. Do not run untrusted captures without the sandbox, and do not expose this image as a public service without the launch gates in `docs/SECURITY.md`. The browser worker requires a long-running host, not an ordinary static or short-lived serverless deployment.

## Development and checks

```bash
npm install
npm run build
npm run typecheck
pytest -q
python -m scripts.check_fixture --data .frameport-check --output fixture-result.json
```

Run the last command with `--offline` only in restricted test environments. It is a test-only file renderer and explicitly annotates its report. It is never imported by the production worker. Offline tests also require the dev dependencies.

For fixture evidence and editable regeneration:

```bash
python -m scripts.check_editing --job fixture-result.json --data .frameport-check --output editing-result.json
python -m scripts.make_preview --job fixture-result.json --data .frameport-check --output studio-preview.html
python -m scripts.check_preview --preview studio-preview.html --output .frameport-ui-check
```

`check_editing` intentionally uses the offline authored-file harness and labels it. CI is configured to attempt real local-fixture browser navigation and an actual npm React build after repository upload. **No GitHub Actions result is claimed until CI runs.** No lockfiles were fabricated; create and commit genuine locks after successful installation.

## Repository and next engineering gate

The source is ready for a private `EmotiveImpact/frameport` repository. No remote repository was created or modified in this delivery. See `STATUS.md`, `ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/CHANGELOG.md` and the experimental bridge adapter under `integrations/framer-plugin`.

The next acceptance gate is a clean run on an authorised, genuinely Framer-published marketing site, followed by the generated React production build and normal-browser preview interaction tests. Expand supported behaviour with small regression fixtures rather than hiding differences behind an unqualified “100%” claim.
