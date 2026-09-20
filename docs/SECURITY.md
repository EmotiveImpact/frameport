# Security and deployment boundaries

## Intended trust model

One trusted operator runs a local worker and converts only sites/assets they own or are authorised to export. The confirmation checkbox is an attestation, not ownership verification or a licence grant. Inspect template, font, media and third-party terms before distributing an export. Do not enter credentials for a source website. Authentication and private/admin-site scraping are intentionally unsupported.

## Implemented controls

Public targets must use HTTP(S), standard ports and no credentials. URL parsing rejects control characters and backslashes. Every DNS answer must be globally routable; private, loopback, link-local, reserved, multicast and IPv4-mapped private addresses are rejected. The fetcher pins connections to a vetted answer, including TLS SNI/certificate verification, and revalidates redirect destinations. It limits request count, concurrency, response size and aggregate bytes. The internal sample server uses an exact server-created exception, never a user-controlled allowlist.

The capture context blocks source writes, WebSockets and service workers. The compiler strips script/handler attributes, unsafe embeds and active SVG constructs, escapes content, disables form delivery and never executes generated React during conversion. Preview paths are containment-checked; only selected types are served. The preview is sandboxed without same-origin privilege. Revision-scoped, expiring HMAC tickets separate image/iframe access from the worker's access key.

Local-only operation rejects non-loopback clients without a key. Remote CLI binding requires a 24-character key. API writes are same-origin and JSON-only. Body size is enforced on streamed bytes as well as Content-Length. Jobs, exports and source readers require authentication when configured. Failed/rebuilding jobs cannot serve completed exports. Host headers are validated. Workspace keys are not persisted in browser storage or placed in preview URLs.

## What remains before public launch

Application checks do not replace browser/OS isolation. Run each untrusted capture in an expendable non-root sandbox with CPU, memory, PID, time and storage limits and a separately enforced egress policy. DNS lookups and Python threads may outlive cooperative cancellation briefly. Chromium vulnerabilities, native codecs and unsupported channels require defence in depth. Never disable the sandbox for untrusted captures.

Public deployment still needs tenant-scoped identity, per-tenant data isolation, durable scheduling and recovery, rate limits/quotas, reliable cleanup, audit logging, abuse reporting, ownership challenges where appropriate, dependency/secret scanning, backups, incident response, external review, and tests of the real network/browser stack. One access key opens one shared workspace; it is not a SaaS authentication system.

## Important operational details

The data folder includes copied content and signed-preview secrets. Keep it private and excluded from Git. URLs can contain sensitive query strings and appear in job records/provenance. Logs and exports should be reviewed before sharing. Old-job cleanup runs at startup; it is not a continuous retention service. The delete API is available for deliberate cleanup.

The Docker configuration has not been executed here. Its sandbox operation depends on host support; do not switch to privileged operation or disable the sandbox to make untrusted sites run. The CI/authoring-only unsandboxed switch is acceptable only for the original controlled fixture, never a public worker.

No safety bypass was used to access the web through restricted Chromium. The offline test renderer reads only the authored local fixture and its generated output. It does not establish live Framer compatibility, complete SSRF protection across all browser internals, or production readiness.
