# Frameport status

**20 September 2026 | Heavier typography and enlarged silver-fold shader | EmotiveImpact/frameport**

## Current tested application code

The updated presentation is implemented on `main`. Tested code commit: `bb2c4d4ff7e84c40172bd1840d05fa8649c07fd0`. [GitHub Actions run 35527121933](https://github.com/EmotiveImpact/frameport/actions/runs/35527121933), job `106121112496`, completed successfully. This status update changes documentation only.

Downloaded evidence artefact `10609698687` was verified against SHA-256 `7e1fbd13df26ecfba20a9ca4f407a1d4d5a283813bd2355f0e7ecea574a9b0ae`. The actual WebGL hero, mobile composition and source editor screenshots were inspected.

## What changed

`web/presentation.css` gives headings, navigation and controls actual semibold weight 600; body, editable text and source code use medium weight 500. Code is at least 12px in the tested layouts. The interface remains black with white/grey text and restrained borders. Mobile headline sizing preserves three lines rather than spilling into five. System font faces vary by operating system; no font binaries or artificial text strokes are included.

The shader was already present, but its earlier rendering was too small and faint. `web/src/eclipse.ts` now renders a wider elliptical silhouette, a stronger silver shoulder and a curved, one-sided folded surface. The hero artwork extends beyond the right viewport edge while copy remains aligned and readable. Narrow tablet and mobile layouts place the artwork below the copy.

This is original native WebGL, not a background image, external texture or embedded Framer template. Pause, reduced motion, offscreen suspension, bounded resolution, disposal and context recovery remain implemented. WebGL-unavailable devices display the explicitly labelled static CSS fallback. The portable preview now includes the new presentation stylesheet and the compiled shader.

## Measured results for this code

The successful CI run passed 78 unit/API cases, 46 existing design/shader checks, 77 additional typography/presentation checks, 10 HTML comparisons, 17 HTML render/disclosure checks, a clean generated React production build, 10 independently built React comparisons and 44 real-browser editing/download acceptance checks. The design, presentation and acceptance reports contain no uncaught browser errors.

The shader tests confirm that actual rendered pixels change while running, stop when paused/offscreen, remain monochrome, and recover after context loss. Typography tests cover the actual HTTP app at 1440, 768, 390 and 320px. A source-font assertion was changed to await settled CSS because asynchronous source loading can replace the selected DOM element. The weight requirement was not lowered. A separate local portable-preview test passed 20 screen/viewport checks; that local test uses CSS fallback, not WebGL or HTTP evidence.

## Preserved scope and limits

The capture engine, compiler, authentication, network policy and sandboxed export preview were not changed. Content editing, revision invalidation and React/HTML downloads remain tested on the original Forma fixture.

CI uses authored fixtures and software WebGL. A genuine Framer-published source, the editor plugin, Docker, production tenant/browser isolation, arbitrary advanced Framer behaviours and every physical GPU/browser remain outside demonstrated coverage. Per-conversion reports do not automatically verify React builds. No public hosted service was deployed in this update.

Run `git pull --ff-only` in the repository, restart the local worker and reload the app. See `docs/PRESENTATION.md` and `docs/MONOCHROME.md` for implementation details.
