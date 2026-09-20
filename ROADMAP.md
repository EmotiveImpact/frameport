# Frameport roadmap

## Implemented developer path

The local studio, persistent queue, authored-site capture/compiler flow, escaped React/HTML source, responsive CSS preservation, local asset collection, HTML visual evidence, limited disclosures, editable text/regeneration, revision invalidation, archives, source browsing and manifest import are implemented. The source bridge adapter is present but not editor-verified. See STATUS.md for test boundaries.

## Gate 1: genuine live-site acceptance

Use authorised Framer-published sites with a recorded expected feature set. Run normal sandboxed browser capture, not the offline harness. Install the exported React dependencies, produce and commit a real lockfile, run strict type checks/build, render the React output and compare it separately from HTML. Exercise the studio against its actual HTTP API, including sandboxed iframes, signed assets, authentication and downloads in supported browsers. Fix every failing feature in a small reproducible regression fixture. No blanket conversion-success claim before this.

## Gate 2: broader conversion coverage

Handle breakpoint-specific DOM variants rather than relying solely on desktop structure and original CSS. Add tested adapters for tabs, carousels, hover menus, overlays, sticky/scroll effects and selected animation patterns. Improve cross-page component reuse, semantic naming, CSS simplification and asset handling for image sets, media, pseudo-elements and font licensing. Surface every unsupported construct precisely.

## Gate 3: project-native context

Run the bridge inside genuine Framer projects; audit SDK/permission coverage. Extend read-only context collection and mapping into the intermediate model. Add opt-in CMS schema/content migration and bindings. A standalone published plugin, full canvas compilation and original source recovery are not already implemented.

## Gate 4: controlled repair

Create deterministic fix rules from failed regression cases. Add optional AI-assisted suggestions behind bounded tests and provenance. Keep extracted data separate from inference. An AI repair loop is not part of the current executable release.

## Gate 5: hosted product

Add proper accounts/workspaces, durable queue and object storage, isolated browser workers with enforced egress, quota/billing/abuse systems, automated retention, deployment observability and a security review. Only then open arbitrary public conversion. A polished studio is not itself the public-worker infrastructure.
