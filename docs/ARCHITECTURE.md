# Architecture

## Running system

One FastAPI process serves the studio and authenticated API, persists jobs in SQLite/WAL and runs a bounded asynchronous queue. The studio uses compiled TypeScript with no runtime UI dependencies. Each conversion gets an unpredictable identifier, private working folder, source model, generated HTML/React directories, visual evidence and export archives. A COMPLETE sentinel and completed job status are both required to serve output. On restart, queued/running jobs become interrupted failures rather than fabricated successes.

## Data flow

`URL / bridge manifest -> permission + URL validation -> browser capture -> structured model -> asset/CSS normalisation -> HTML + React generation -> HTML rendering/comparison -> report -> ZIP`

`Text edits -> validated stable field IDs -> revision increment + download/ticket invalidation -> model update -> generation -> new comparisons -> new ZIP`

The browser's HTTP traffic is intercepted and fulfilled through the pinned-IP fetcher. It checks every destination, including redirect targets, and requires all DNS answers to be public. It connects to the vetted IP, preserving TLS SNI and verification for HTTPS. Source requests do not carry user credentials or cookies. Non-GET requests, WebSockets, downloads and service workers are not supported. The internally created sample origin is the only private-network exception and cannot be selected through the public URL field.

## Model and compiler

Capture reads the 1440px rendered DOM, original stylesheets, current images, page metadata, links and warnings. Five source snapshots establish explicitly bounded visual evidence. The model is versioned JSON: pages, DOM-like nodes, attributes, text fields, styles, assets, issues and optional bridge context. This is not a recovered Framer design tree.

The compiler traverses an allowlisted node/attribute model and emits escaped HTML or JSX from nodes. It does not concatenate unescaped source text, execute generated source code, inject HTML strings into React, or copy proprietary JavaScript bundles. Section boundaries become separate React components. Text is normalised into JSON keyed by stable capture IDs. Original CSS remains the layout source of truth. Local assets use content-derived names, with MIME validation and SVG cleanup.

Only Frameport-owned disclosure/form-safety JavaScript is emitted. Native HTML and CSS behaviours remain native. Complex interaction inference and an automatic AI repair loop are not implemented. A template's reusable Framer component relationships are not recovered; same-looking sections on different pages can remain separate components.

## Validation

The normal validator serves the generated HTML from a temporary loopback server in a separate context. Only its origin may load. It captures the same widths and compares true RGB images, rejects mismatched dimensions, checks broken images and simple disclosures, and records all blocked requests/browser errors. Source and export are frozen consistently for screenshot comparison, but the freeze stylesheet is never shipped.

The authoring environment blocked browser navigation. Test-only `tests/offline_browser.py` substituted loading known local files via `set_content`, without changing administrator policy or fetching blocked sites. Its source URL/style metadata restoration is explicit and its reports identify the substitution. This verifies compiler/rendered-output behaviour, not normal navigation, source hydration or original Framer runtime capture. The production worker does not import this harness.

## Package layout

- `frameport/app.py`, `store.py`, `models.py`, `config.py`: API, lifecycle and contracts.
- `frameport/engine/network.py`: bounded, pinned-DNS fetcher.
- `capture.py`, `extract.js`: browser capture and structured extraction.
- `assets.py`, `compiler.py`: sanitisation, local assets and code generation.
- `validate.py`, `pipeline.py`: actual evidence, revision lifecycle and packaging.
- `web/src/app.ts`, `web/style.css`, `web/dist/app.js`: studio source and precompiled app.
- `integrations/framer-plugin/export.ts`: experimental read-only project bridge adapter.
- `fixtures/forma`: original two-page regression input.
- `tests`, `scripts`: contract/security tests, measured fixture checks, source syntax and UI checks.

## Deployment boundary

This release deliberately has one shared workspace, one worker, local storage and an optional access key. It is not a multi-tenant product. Production requires independently isolated browser jobs, network-level egress enforcement, durable queue/storage, identity/tenant isolation, operational budgets and monitored retention. The app shell can be separated later, but browser captures cannot be hosted as a static website alone.
