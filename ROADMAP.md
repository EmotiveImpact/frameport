# Frameport roadmap

## Completed foundation

The local studio, persistent queue, escaped HTML/React generator, local assets, HTML visual evidence, source browser, text editing/regeneration, revision invalidation and archives are implemented. The original Forma fixture now passes actual HTTP capture, a clean React production build, independent HTML/React comparisons and the full authenticated browser journey. See `STATUS.md` for the verified commit and run.

## Next: genuine live-site acceptance

Use an authorised Framer-published marketing site with a recorded expected feature set. Capture it with the normal sandboxed worker, build its React export and compare that output separately from HTML. Exercise links, mobile navigation, forms and visible interactions. Turn each discrepancy into a small regression fixture. The existing sample's successful CI is not a substitute for this gate.

## Broader conversion coverage

Reconstruct breakpoint-specific DOM variants. Add tested adapters for tabs, carousels, overlays and selected scroll/motion patterns. Improve cross-page component reuse, semantic naming, CSS simplification, responsive images, media and asset provenance. Keep unsupported constructs visible rather than silently flattening them.

## Project-native context

Test the read-only bridge inside genuine Framer projects. Extend its metadata mapping and add opt-in CMS schema/content migration with actual bindings. The current JSON importer does not compile the original Framer canvas or automatically recover its reusable abstractions.

## Controlled repair and hosted product

Build deterministic repair rules from observed failures before adding optional, bounded AI suggestions. For public hosting, add isolated browser workers, enforced egress, tenant identity and storage isolation, durable scheduling, billing/quotas, abuse controls, monitored retention and external review. Docker and public operations are not verified merely because the studio works.
