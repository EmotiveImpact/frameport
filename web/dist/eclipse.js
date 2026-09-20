export const vertexSource = `
attribute vec2 aPosition;
void main() { gl_Position = vec4(aPosition, 0.0, 1.0); }
`;
// All smoothstep edges are ascending. Coordinates are in drawing-buffer pixels,
// independent of CSS size/DPR, and the triangle covers the entire clip space.
export const fragmentSource = `
precision highp float;
uniform vec2 uResolution;
uniform float uTime;
uniform float uIntensity;
void main() {
  vec2 p = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y;
  p -= vec2(0.10, 0.0);
  float turn = -0.09 + 0.035 * sin(uTime * 0.10);
  float c = cos(turn), s = sin(turn);
  vec2 q = mat2(c, -s, s, c) * p;
  q /= vec2(1.40, 0.88);
  float r = length(q);
  float radius = 0.45;
  float d = r - radius;
  float aa = 1.3 / uResolution.y;
  float inside = 1.0 - smoothstep(-aa, aa, d);
  vec2 n = q / max(r, 0.0001);

  // A broad silver shoulder at the left, with a brighter lower-right fold.
  // The composition intentionally continues beyond the right viewport edge.
  float shoulder = pow(max(dot(n, normalize(vec2(-0.76, 0.65))), 0.0), 3.0);
  float underside = pow(max(dot(n, normalize(vec2(0.62, -0.78))), 0.0), 3.5);
  float lighting = max(shoulder, underside * 1.18);
  float rim = exp(-abs(d) / max(0.0020, aa)) * lighting;
  float innerRim = exp(-abs(d) / 0.014) * lighting * inside;
  float halo = exp(-abs(d) / 0.022) * lighting * 0.06;

  // Curved, one-sided material falloff, not a wireframe slash across a sphere.
  float fold = q.y + q.x * 0.82 - 0.09 * (q.x * q.x - 0.10)
             + 0.018 * sin(uTime * 0.10 + q.x * 2.0);
  float along = smoothstep(-0.34, 0.40, q.x);
  float sheet = exp(-max(fold, 0.0) / (0.048 + along * 0.040))
              * smoothstep(-aa, 0.012, fold);
  float crease = exp(-abs(fold) / max(0.0030, aa));
  float edgeFalloff = 0.36 + 0.64 * smoothstep(0.06, radius, r);
  float surface = inside * edgeFalloff *
    (sheet * (0.13 + 0.42 * along) + crease * (0.05 + 0.53 * along));
  float luminance = (rim * 0.92 + innerRim * 0.32 + halo + surface) * uIntensity;
  // Preserve true black beyond the local edge. No tinted bloom or grey fog.
  luminance *= 1.0 - smoothstep(0.50, 0.58, r);
  gl_FragColor = vec4(vec3(clamp(luminance, 0.0, 1.0)), 1.0);
}
`;
export function mountEclipse(canvas, options = {}) {
    const host = canvas.parentElement;
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    const connection = navigator.connection;
    let paused = options.paused ?? false;
    let disposed = false, lost = false, inView = true, raf = 0, frames = 0;
    let elapsed = 0, previous = 0, lastDraw = 0;
    let gl = null;
    let program = null, buffer = null;
    let time = null, resolution = null;
    const shaders = [];
    const rawIntensity = options.intensity ?? 1;
    const intensity = Number.isFinite(rawIntensity) ? Math.max(0, Math.min(1.5, rawIntensity)) : 1;
    const still = () => reduced.matches || !!connection?.saveData;
    const available = () => !!gl && !!program && !lost && !disposed;
    const active = () => available() && !paused && !still() && !document.hidden && inView;
    function publish() {
        const renderer = available() ? 'webgl' : 'fallback';
        const motion = !available() ? 'unavailable' : still() ? 'reduced' : paused ? 'paused' : document.hidden || !inView ? 'hidden' : 'running';
        host.dataset.renderer = renderer;
        host.dataset.motion = motion;
        options.onState?.({ renderer, motion });
    }
    function release() {
        if (!gl)
            return;
        if (buffer)
            gl.deleteBuffer(buffer);
        if (program)
            gl.deleteProgram(program);
        shaders.splice(0).forEach(shader => gl.deleteShader(shader));
        buffer = null;
        program = null;
    }
    function prepare() {
        if (!gl)
            return;
        release();
        try {
            const precision = gl.getShaderPrecisionFormat(gl.FRAGMENT_SHADER, gl.HIGH_FLOAT);
            for (const [type, source] of [[gl.VERTEX_SHADER, vertexSource], [gl.FRAGMENT_SHADER, precision?.precision ? fragmentSource : fragmentSource.replace('highp', 'mediump')]]) {
                const shader = gl.createShader(type);
                if (!shader)
                    throw new Error('Shader allocation failed');
                shaders.push(shader);
                gl.shaderSource(shader, source);
                gl.compileShader(shader);
                if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS))
                    throw new Error('Shader compilation failed');
            }
            program = gl.createProgram();
            buffer = gl.createBuffer();
            if (!program || !buffer)
                throw new Error('WebGL allocation failed');
            shaders.forEach(shader => gl.attachShader(program, shader));
            gl.linkProgram(program);
            if (!gl.getProgramParameter(program, gl.LINK_STATUS))
                throw new Error('Shader link failed');
            gl.useProgram(program);
            gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
            gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
            const position = gl.getAttribLocation(program, 'aPosition');
            gl.enableVertexAttribArray(position);
            gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
            resolution = gl.getUniformLocation(program, 'uResolution');
            time = gl.getUniformLocation(program, 'uTime');
            gl.uniform1f(gl.getUniformLocation(program, 'uIntensity'), intensity);
            gl.disable(gl.DEPTH_TEST);
            gl.disable(gl.BLEND);
        }
        catch {
            release();
        }
    }
    function resize() {
        if (!available())
            return;
        const box = canvas.getBoundingClientRect();
        if (!box.width || !box.height)
            return;
        const ratio = Math.min(devicePixelRatio || 1, box.width < 600 ? 1 : 1.5, Math.sqrt(1400000 / (box.width * box.height)));
        const width = Math.max(1, Math.round(box.width * ratio)), height = Math.max(1, Math.round(box.height * ratio));
        if (canvas.width !== width || canvas.height !== height) {
            canvas.width = width;
            canvas.height = height;
        }
        gl.viewport(0, 0, width, height);
        gl.uniform2f(resolution, width, height);
        draw();
    }
    function draw() {
        if (!available())
            return;
        gl.uniform1f(time, elapsed);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
        canvas.dataset.frames = String(++frames);
    }
    function tick(now) {
        raf = 0;
        if (!active()) {
            previous = 0;
            publish();
            return;
        }
        if (now - lastDraw >= 1000 / 30) {
            elapsed += previous ? Math.min((now - previous) / 1000, 0.1) : 0;
            previous = now;
            lastDraw = now;
            draw();
        }
        raf = requestAnimationFrame(tick);
    }
    function reconcile() {
        if (disposed)
            return;
        if (raf)
            cancelAnimationFrame(raf);
        raf = 0;
        previous = 0;
        publish();
        if (active())
            raf = requestAnimationFrame(tick);
        else if (available() && !document.hidden && inView)
            draw();
    }
    const onLost = (event) => { event.preventDefault(); lost = true; reconcile(); };
    const onRestored = () => { lost = false; prepare(); resize(); reconcile(); };
    canvas.addEventListener('webglcontextlost', onLost);
    canvas.addEventListener('webglcontextrestored', onRestored);
    try {
        gl = canvas.getContext('webgl', { alpha: false, antialias: false, depth: false, stencil: false, powerPreference: 'low-power' });
    }
    catch { /* CSS fallback remains visible. */ }
    prepare();
    const sizeObserver = new ResizeObserver(resize);
    sizeObserver.observe(canvas);
    const visibilityObserver = new IntersectionObserver(entries => { inView = entries[0]?.isIntersecting ?? true; reconcile(); });
    visibilityObserver.observe(canvas);
    reduced.addEventListener('change', reconcile);
    document.addEventListener('visibilitychange', reconcile);
    window.addEventListener('resize', resize);
    resize();
    reconcile();
    return {
        setPaused(value) { paused = value; reconcile(); },
        dispose() {
            if (disposed)
                return;
            disposed = true;
            if (raf)
                cancelAnimationFrame(raf);
            sizeObserver.disconnect();
            visibilityObserver.disconnect();
            reduced.removeEventListener('change', reconcile);
            document.removeEventListener('visibilitychange', reconcile);
            window.removeEventListener('resize', resize);
            canvas.removeEventListener('webglcontextlost', onLost);
            canvas.removeEventListener('webglcontextrestored', onRestored);
            release();
            gl?.getExtension('WEBGL_lose_context')?.loseContext();
        }
    };
}
