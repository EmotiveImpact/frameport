# Monochrome studio and eclipse artwork

20 September 2026. The approved visual direction is implemented in the actual Frameport studio, not in an embedded Framer page or an image-only mock-up.

## Design

The global background is black. Navigation moves to the top, including mobile workspace access. Typography, white primary buttons, grey secondary actions and hairline borders provide the hierarchy. Conversion, project history, source browsing, content editing, progress, reports and documentation share the same monochrome styling. The site being inspected inside the preview retains its original appearance.

The home page combines the hero with the existing conversion form and real project history. The primary action focuses the URL input. The sample action runs the authored Forma fixture. Template galleries, billing screens, invented success metrics and testimonial badges have not been added.

## Original shader

`web/src/eclipse.ts` contains an original WebGL 1 vertex/fragment shader and its lifecycle controller. This is an interpretation of the approved luminous folded crescent, not the source shader or proprietary artwork from Monitor. It uses one full-screen triangle, no textures, no copied site scripts and no new runtime dependency. `web/dist/eclipse.js` is the corresponding compiled module.

The effect occupies the hero only. The background is not tinted or filled with grey fog. Greyscale rim lighting and a curved interior fold move slowly, while the body of the app remains still.

`mountEclipse(canvas, { paused, intensity, onState })` returns `setPaused()` and `dispose()`. Intensity defaults to one and is bounded between zero and 1.5. All smoothstep bounds are ordered; screen coordinates use drawing-buffer resolution rather than assuming a two-unit plane fills a pixel-sized orthographic viewport.

The animation is capped at approximately 30 frames per second. Pixel density is capped at 1.5, or one on smaller canvases, with an approximately 1.4-million-pixel drawing budget. Offscreen and hidden-tab drawing stops. Reduced-motion and data-saving preferences render a still frame. A visible pause control is supplied. Resize, context loss/restoration and route disposal are handled explicitly, including cancelling animation and releasing GPU resources.

A CSS fallback remains visible when WebGL is unavailable. It does not disable forms, navigation or downloads. The pause control identifies static artwork rather than pretending a shader is running.

## Verification

`scripts/check_design.py --software-gl` runs the actual local HTTP app using an explicitly selected software WebGL renderer for repeatable CI. It checks shader compilation, changing rendered pixels, monochrome output, black negative space, pause, offscreen suspension, reduced motion, context recovery, route cleanup, pixel limits, responsive navigation and fallback form usability. No external source website is visited by this test.

The existing fixture, generated React build, HTML/React visual comparisons and authenticated editing/download acceptance remain in CI. Software rendering is not a guarantee for every physical GPU or browser. Authored-fixture conversion is not a benchmark of arbitrary live Framer sites.

The portable HTML preview embeds the compiled shader module and measured fixture data. It is a read-only demonstration without a worker. Run `bash scripts/start.sh` from the repository to use the actual conversion tool.
