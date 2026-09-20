# Frameport status

**20 September 2026 | 0.1.0 developer release | EmotiveImpact/frameport**

## Repository and verified code

The complete source has been pushed to `main`. Tested code commit: `bf340ab3f8a8ee27c45fd7ec9ac58e385c844b1c`. [GitHub Actions run 35504470191](https://github.com/EmotiveImpact/frameport/actions/runs/35504470191) completed successfully. Any subsequent documentation-only commit does not change this tested code tree.

The earlier statement that no remote repository was changed is obsolete. The owner created the repository, and the source and subsequent fixes were pushed on 20 September 2026. No hosted service was deployed.

## Working and demonstrated

The original two-page Forma fixture passes real HTTP capture, HTML generation, clean React dependency installation and production build, independent five-width visual comparisons, authenticated studio access, sandboxed preview, mobile disclosures, source viewing, content edits, revision invalidation and actual browser downloads of both formats.

After rebuilding, both the editor and source viewer now display the saved revision rather than cached text. This has its own browser regression check. Generated Vite was updated to 6.4.3; the observed dependency audit reported no vulnerabilities.

Measured results: 75 unit/API cases, 10 HTML comparisons, 17 HTML render/disclosure checks, 10 built-React comparisons and 44 browser acceptance checks passed. No uncaught browser errors occurred in that acceptance run. See `docs/TEST-REPORT.md` and `docs/evidence/ci-summary.json`.

## Still outside verified coverage

A genuine Framer-published site, the plugin inside Framer, Docker operation, production browser/tenant isolation, advanced Framer motion and breakpoint-specific DOM reconstruction remain unverified or unfinished. CI's authored-fixture browser is not a production sandbox assurance. Ordinary per-conversion reports still do not automatically verify React builds.

## Next acceptance target

Run an authorised published Framer URL through the normal sandboxed worker. Compare its independently built React and HTML outputs and record unsupported features as reproducible fixtures. The current green sample workflow is the foundation for that test, not a claim that every Framer site converts faithfully.
