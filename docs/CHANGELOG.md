# Change log and issues corrected

## 0.1.0 · 20 September 2026

Implemented the single-workspace studio, persistent queue, URL capture, limited same-origin crawl, semantic source generator, HTML/React outputs, local asset handling, comparison/report views, editable text, export regeneration, archive delivery, signed previews and the JSON bridge importer. Added the original Forma fixture, an experimental Framer adapter, development scripts and CI configuration.

During this build:

1. TypeScript initially compiled the UI as a global script. Making it an explicit module fixed global declaration and `history` naming collisions.
2. The environment rejected Chromium HTTP navigation by administrator policy. Tests were moved to a clearly labelled authored-file rendering harness; the policy was not changed. Normal capture remains a separate unverified integration gate.
3. A screenshot clip initially captured only the viewport despite reporting document height. Full-page capture is now explicit and PNG dimensions must exactly match declared coverage. All delivered evidence was regenerated after that fix.
4. A test-loader `/index.html` alias created a duplicate fixture page. The loader now preserves requested URL context, the crawler deduplicates index aliases and internal link rewriting recognises them.
5. The screenshot-freeze stylesheet could have leaked into exports. Freeze styles are now tagged and excluded from extracted source styles.
6. Mobile disclosure checks originally ran only at desktop width. They now run at 390 and 1440px where controls are visible.
7. Numeric JSX attributes and `playsInline` are emitted with suitable value types. Inline important declarations produce a React review warning rather than an unstated assumption.
8. API request-size protection now counts actual streamed bytes, not only the Content-Length header.
9. The live source reader now agrees with its file listing about SVG and `.gitignore` files.
10. Small-screen decorative artwork overlapped the headline. It is hidden at narrow widths and the UI checks were rerun.

See TEST-REPORT.md for actual results and unverified areas. No live deployment, remote push or CI pass is implied by this change log.
