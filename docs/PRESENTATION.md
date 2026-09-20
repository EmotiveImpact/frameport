# Readable type and restored visual emphasis


The September 20 reference refinement uses a single `web/presentation.css` layer after the structural stylesheet. Actual semibold weights (600) now cover the hero, page headings, section headings, navigation and controls. Body and editor copy use medium weight (500); source code uses 500 at 12px with matching line-number spacing. No font files, artificial text outlines or text glow are introduced. Available system font faces can vary by operating system.

The original live shader remains `web/src/eclipse.ts`, not an embedded image or remote Framer effect. The old interpretation was a small, faint closed disc. Its replacement has wider elliptical proportions, a broad silver shoulder and a brighter one-sided folded surface; the composition extends beyond the right viewport edge. It remains greyscale on true black. The CSS fallback is also enlarged, and still explicitly says Static artwork on devices without WebGL. The controller's pause, reduced-motion, hidden/offscreen suspension, context recovery and disposal paths are unchanged.

`scripts/check_presentation.py` adds actual HTTP checks of weights, layout bounds and the rendered silver surface, plus source/editor/report views at desktop and mobile widths using the real authored fixture. Its software-WebGL screenshots must pass alongside the existing shader lifecycle and conversion checks. Local authored-document checks in restricted environments are not presented as GPU or HTTP evidence.
