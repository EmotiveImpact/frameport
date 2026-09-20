# Frameport status

**20 September 2026 | Monochrome studio and original eclipse shader | EmotiveImpact/frameport**

## Current code and GitHub verification

The approved black studio is implemented on `main`, including the original live WebGL hero artwork. Tested code commit: `4710254f4c773d261edb604c46ead6335d368525`. [GitHub Actions run 35514576325](https://github.com/EmotiveImpact/frameport/actions/runs/35514576325), job `106088235326`, completed successfully. This status update is documentation only.

The latest downloaded evidence archive is artefact `10606232397`, SHA-256 `315144f2552d073cd67d782609399063fc0f4965833b791d6d76a1499895834c`. Its actual desktop and mobile screenshots were inspected. A hidden-scroll-container issue that clipped the heading during canvas inspection was corrected with non-scrolling hero clipping and a dedicated regression assertion.

## Delivered design

Pure black background, white and grey typography, top navigation instead of a sidebar, restrained borders and white primary buttons. The design covers the home/conversion screen, project history, progress, source code, content editor, verification and documentation. The original website inside the preview is not recoloured.

`web/src/eclipse.ts` implements the original greyscale folded-disc shader in native WebGL. There is no new runtime dependency, copied Monitor source, external texture or embedded Framer template. The hero supports manual pause, reduced motion, offscreen suspension, bounded drawing resolution, context recovery and a static CSS fallback. See `docs/MONOCHROME.md` for the implementation and operating limits.

## Measured results for this code

The latest CI passed 75 unit/API cases, 46 design/shader/responsive checks, 10 HTML comparisons, 17 HTML render/disclosure checks, a clean generated React build, 10 independently built React comparisons and 44 real-browser editing/download acceptance checks. The design and acceptance reports contain no uncaught browser errors. The generated dependency audit reported zero vulnerabilities at that run.

A separate local portable-preview check passed 20 screen/viewport checks and source/content assertions. That local test used the authored HTML preview and a CSS fallback, not live browser-to-worker integration or GPU rendering. The WebGL verification above came from explicit software rendering in CI.

## Preserved functionality and boundaries

The capture engine, compiler, authentication, network policies and sandboxed export preview were not changed by the redesign. Real content editing, revision invalidation and browser downloads of both React and HTML remain tested on the original Forma fixture.

A genuinely Framer-published source, the plugin inside Framer, Docker operation, production browser/tenant isolation and arbitrary advanced Framer behaviours remain outside demonstrated coverage. CI's authored fixture and software WebGL tests do not establish compatibility with every website, physical GPU or browser. Per-conversion reports still do not automatically verify React production builds.

## Running the updated tool

From the repository folder, run `git pull --ff-only`, then `bash scripts/start.sh`, and open `http://127.0.0.1:8040`. The source and compiled studio are on GitHub. No hosted public conversion service was deployed in this delivery.
