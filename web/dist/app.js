import { parseRoute, viewPath, projectPath, safeReturnPath } from './router.js';
import { connectionBanner, settingsView, loginView, problemView, exportView } from './platform-views.js';
import { mountEclipse } from './eclipse.js';
const offline = window.__FRAMEPORT_PREVIEW__;
let routeGeneration = 0, fileGeneration = 0, submitting = false;
let activePath = '/';
class ApiError extends Error {
    status;
    constructor(message, status) {
        super(message);
        this.status = status;
    }
}
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const paths = {
    grid: '<rect x="3" y="3" width="7" height="7" rx="1.6"/><rect x="14" y="3" width="7" height="7" rx="1.6"/><rect x="3" y="14" width="7" height="7" rx="1.6"/><rect x="14" y="14" width="7" height="7" rx="1.6"/>',
    layers: '<path d="m12 3 10 5-10 5L2 8l10-5Z"/><path d="m2 12 10 5 10-5M2 16l10 5 10-5"/>',
    book: '<path d="M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-3H4V4Zm16 0h-4a3 3 0 0 0-3 3v14a4 4 0 0 1 4-3h3V4Z"/>',
    plus: '<path d="M12 5v14M5 12h14"/>', arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>', up: '<path d="M6 18 18 6M6 6h12v12"/>',
    globe: '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
    code: '<path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 16"/>', check: '<path d="m5 12 4 4L19 6"/>', chevron: '<path d="m9 5 7 7-7 7"/>', down: '<path d="m6 9 6 6 6-6"/>',
    shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
    monitor: '<rect x="3" y="3" width="18" height="13" rx="2"/><path d="M8 21h8m-4-5v5"/>', tablet: '<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M11 18h2"/>', phone: '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/>',
    download: '<path d="M12 3v12m-5-5 5 5 5-5M4 15v6h16v-6"/>', close: '<path d="m6 6 12 12M6 18 18 6"/>', back: '<path d="M20 12H4m7-7-7 7 7 7"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>', refresh: '<path d="M20 7a9 9 0 1 0 1 8M20 2v5h-5"/>',
    file: '<path d="M14 2H5v20h14V7l-5-5Z"/><path d="M14 2v6h5M8 13h8M8 17h6"/>', folder: '<path d="M3 5h7l2 3h9v12H3V5Z"/>', copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M15 8V3H3v13h5"/>',
    sliders: '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="9" cy="18" r="2"/>',
    search: '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6"/>', spark: '<path d="m12 2 2.7 7.3L22 12l-7.3 2.7L12 22l-2.7-7.3L2 12l7.3-2.7L12 2Z"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>', warning: '<path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v5m0 3v1"/>',
    play: '<path d="m8 4 12 8-12 8V4Z"/>', split: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="M12 2v20"/>', image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="2"/><path d="m3 17 5-5 4 4 4-6 5 7"/>',
    edit: '<path d="m15 4 5 5M4 20l5-1L21 7l-5-5L4 14v6Z"/>', trash: '<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>',
    terminal: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m6 8 4 4-4 4m7 0h5"/>', lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 4v3"/>', upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6"/>'
};
function icon(name, size = 18) { return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.file}</svg>`; }
function mark() { return '<svg viewBox="0 0 32 32" width="25" height="25" aria-hidden="true"><path d="M4 4h24v8H12v5h12v7H12v4H4V4Z" fill="currentColor"/><path d="m21 17 7 5-7 6V17Z" fill="currentColor"/></svg>'; }
function reactMark(size = 23) { return `<svg width="${size}" height="${size}" viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.3" aria-hidden="true"><ellipse cx="16" cy="16" rx="14" ry="5.5"/><ellipse cx="16" cy="16" rx="14" ry="5.5" transform="rotate(60 16 16)"/><ellipse cx="16" cy="16" rx="14" ry="5.5" transform="rotate(120 16 16)"/><circle cx="16" cy="16" r="2.2" fill="currentColor" stroke="none"/></svg>`; }
const state = { view: 'overview', tab: 'preview', jobs: offline ? [offline.job] : [], job: null, worker: false, auth: false, key: '', width: 1440, page: 'p0', mode: 'compare', split: 50, files: [], code: '', file: '', contents: [], edits: new Map(), historyFilter: '', sourceTarget: 'react', poll: 0, formTab: 'url', zoom: false, loading: false, problem: '', problemKind: 'offline', filterStatus: 'all', health: { worker: 'checking', canConvert: false, authRequired: false, storage: 'not-connected' } };
let toastTimer = 0;
function toast(message) { const el = $('#toast'); if (!el)
    return; el.textContent = message; el.classList.add('visible'); clearTimeout(toastTimer); toastTimer = window.setTimeout(() => el.classList.remove('visible'), 4300); }
async function api(path, options = {}) {
    if (offline) {
        if (options.method && options.method !== 'GET')
            throw new Error('This is the portable preview. Start the included Frameport worker to run conversions and save edits.');
        if (path === '/api/jobs' || path === '/api/projects')
            return [offline.job];
        if (path === '/api/session')
            return { authenticated: true, authRequired: false };
        if (path === '/api/health')
            return { worker: 'preview', authRequired: false };
        if (path.includes('/files')) {
            const files = path.includes('target=html') ? offline.htmlFiles : offline.files;
            return Object.keys(files).map(p => ({ path: p, bytes: files[p].length }));
        }
        if (path.includes('/file?')) {
            const u = new URL(path, 'http://frameport.local/');
            const p = u.searchParams.get('path') || '';
            return { path: p, content: (u.searchParams.get('target') === 'html' ? offline.htmlFiles : offline.files)[p] || '' };
        }
        if (path.endsWith('/content'))
            return offline.content;
        return offline.job;
    }
    const response = await fetch(path, { credentials: 'same-origin', ...options, headers: { 'Content-Type': 'application/json', ...(state.key ? { 'Authorization': `Bearer ${state.key}` } : {}), ...options.headers } });
    if (!response.ok) {
        let msg = `Request failed (${response.status})`;
        try {
            const body = await response.json();
            msg = typeof body.detail === 'string' ? body.detail : body.detail?.map((x) => x.msg).join(';') || msg;
        }
        catch { }
        if (response.status === 401)
            state.auth = true;
        throw new ApiError(msg, response.status);
    }
    return response.json();
}
async function boot() {
    state.loading = true;
    render();
    if (offline) {
        state.loading = false;
        state.health = { worker: 'preview', canConvert: false, authRequired: false };
        render();
        return;
    }
    await refreshHealth();
    await applyRoute(location.pathname + location.search);
}
function statusBadge(job) { const status = job.status === 'completed' ? (job.report?.visualPassed ? 'Visually checked' : 'Needs review') : job.status === 'running' ? job.stage : job.status; return `<span class="badge ${job.status === 'completed' ? (job.report?.visualPassed ? 'green' : 'amber') : job.status === 'failed' ? 'red' : 'neutral'}">${job.status === 'completed' ? icon(job.report?.visualPassed ? 'check' : 'warning', 12) : icon(job.status === 'running' ? 'refresh' : 'clock', 12)}${esc(status)}</span>`; }
function title(job) { return job.request.name || job.report?.pages[0]?.title || 'Untitled conversion'; }
function relativeDate(timestamp) { return new Date(timestamp * 1000).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }); }
function shell(content) { return `<a class="skip-link" href="#main-content">Skip to content</a><header class="topbar"><a href="/" class="brand" data-view="overview" aria-label="Frameport home">${mark()}<span>Frameport</span></a><nav class="main-nav" aria-label="Main navigation">${[['overview', 'Home'], ['history', 'Projects'], ['docs', 'Docs']].map(([v, label]) => `<button data-view="${v}" ${state.view === v ? 'aria-current="page"' : ''}>${label}</button>`).join('')}</nav><div class="top-actions"><button class="icon-button" id="find-button" aria-label="Find a conversion">${icon('search', 17)}</button><button class="workspace" id="workspace-button" aria-label="Connect workspace"><span class="dot ${state.worker ? 'online' : ''}"></span><span class="workspace-label">${offline ? 'Preview' : state.auth ? 'Sign in' : state.worker ? 'My workspace' : 'Service status'}</span><span class="avatar">E</span></button></div></header>${offline || state.health.worker === 'checking' ? '' : connectionBanner(state.health, state.auth)}<main class="main" id="main-content" tabindex="-1"><div class="page ${state.view === 'project' ? 'project-page' : ''}" data-route-view="${esc(state.view)}">${content}</div><footer class="app-footer"><a data-view="overview" href="/">${mark()} Frameport</a><span>Your design. Your code.</span><a data-route="/settings" href="/settings">${offline ? 'Recorded sample preview' : 'Workspace status'}</a></footer></main><div id="modal-root"></div>`; }
function overview() { return `<section class="welcome" aria-labelledby="hero-title"><div class="hero-copy"><div class="eyebrow">FRAMER TO CODE</div><h1 id="hero-title">Design<br>without limits.<br><span>Own the code.</span></h1><p>Take your Framer site into editable React or HTML.<br>Keep the design. Make the next move yours.</p><div class="hero-actions"><button class="primary" id="start-converting">Start converting ${icon('arrow', 17)}</button><button class="text-button" id="hero-demo">${icon('play', 15)}Explore the sample</button></div></div><div class="hero-visual" data-renderer="fallback" aria-hidden="true"><div class="eclipse-fallback"></div><canvas id="hero-shader"></canvas></div><div class="hero-caption">SAME VISION.<br>MORE FREEDOM.</div><div class="hero-bottom"><div><span class="tech-caption">A NEW HOME FOR YOUR NEXT IDEA</span><div class="technology-list"><span>${reactMark(21)}React</span><span class="typescript-mark">TS <span>TypeScript</span></span><span>${icon('code', 21)}HTML + CSS</span></div></div><button class="motion-control" id="motion-toggle" aria-pressed="false" aria-label="Pause background animation">Pause motion</button></div></section><section class="conversion-section" id="convert"><div class="section-intro"><div class="eyebrow">01 / START SOMETHING</div><h2>Add your Framer site.</h2><p>A published website in. An editable project out.</p></div>${conversionPanel()}<p class="scope-note">Published-site reconstruction, not recovery of Framer’s original source. Review unsupported interactions before publishing.</p></section><section class="recent-section"><div class="section-title"><div><div class="eyebrow">02 / KEEP BUILDING</div><h2>${state.jobs.length ? 'Your recent projects.' : 'Good design is just the beginning.'}</h2></div>${state.jobs.length ? '<button class="text-button" data-view="history">All projects ' + icon('arrow', 16) + '</button>' : ''}</div>${state.jobs.length ? `<div class="recent-grid">${state.jobs.slice(0, 3).map(jobCard).join('')}</div>` : `<div class="first-project"><div><span class="eyebrow">THE INCLUDED SAMPLE</span><h3>Meet Forma.</h3><p>An original two-page test site. Explore the capture, inspect the code and make a change.</p><button class="secondary" id="run-demo">${icon('play', 14)}Convert the sample ${icon('arrow', 14)}</button></div><div class="sample-art" aria-hidden="true"><span>forma®</span><div class="sample-shape"></div><small>INDEPENDENT BY DESIGN</small></div></div>`}</section><section class="below-converter"><div class="mini-feature">${icon('layers', 22)}<h3>Not a wrapper.</h3><p>Separate components, pages and editable content. Continue in your own codebase.</p></div><div class="mini-feature">${icon('split', 22)}<h3>See the difference.</h3><p>Compare captured HTML at five widths. Review what matches and what needs attention.</p></div><div class="mini-feature">${icon('code', 22)}<h3>Take it from here.</h3><p>Download the files, inspect the report and build your next chapter.</p></div></section>`; }
function conversionPanel() { return `<section class="convert-card" aria-label="New conversion"><div class="convert-card-head"><div class="input-tabs"><button id="url-tab" class="${state.formTab === 'url' ? 'selected' : ''}" aria-pressed="${state.formTab === 'url'}">Website URL</button><button id="bridge-tab" class="${state.formTab === 'bridge' ? 'selected' : ''}" aria-pressed="${state.formTab === 'bridge'}">Project manifest</button></div><span class="privacy-note">${icon('lock', 13)}Your workspace</span></div>${state.formTab === 'url' ? `<form id="conversion-form"><label class="input-label" for="url">Published website URL</label><div class="url-input-wrap">${icon('globe', 18)}<input id="url" type="url" placeholder="https://your-site.framer.website" autocomplete="url" spellcheck="false" required><button class="primary convert-button" type="submit">Convert site ${icon('arrow', 17)}</button></div><div class="input-bottom"><span>Use a published URL, not a Framer editor link.</span><button type="button" class="text-button" id="options-toggle" aria-expanded="false" aria-controls="export-options">${icon('sliders', 14)}Export settings</button></div><div class="export-options" id="export-options" hidden><label>Project name<input id="project-name" placeholder="My next project" maxlength="80"></label><label>Page limit<select id="max-pages"><option value="1">1 page</option><option value="3" selected>Up to 3 pages</option><option value="8">Up to 8 pages</option></select></label><label class="check-option"><input id="crawl" type="checkbox" checked>Follow same-site links</label></div><label class="permission"><input id="permission" type="checkbox" required><span>I own this website or have permission to export its design and assets.</span></label></form>` : `<div class="bridge-panel"><span>${icon('upload', 28)}</span><div><h3>Bring your project context.</h3><p>Import a Frameport JSON manifest. A published URL is still required. CMS records are included as reference content, not live bindings.</p><label class="secondary upload-label">Choose manifest.json<input id="manifest-input" type="file" accept="application/json,.json" hidden></label><button class="text-button" id="bridge-help">Bridge guide ${icon('arrow', 14)}</button></div></div>`}<div class="output-strip"><span>IN YOUR EXPORT</span><div>${reactMark(17)}React + TypeScript</div><div>${icon('code', 16)}HTML + CSS</div><div>${icon('shield', 16)}Visual evidence</div></div></section>`; }
function convertView() { return `<section class="convert-intro"><div class="eyebrow">NEW CONVERSION</div><h1>Give your next project<br>its own codebase.</h1><p>Start with a published URL or an authorised project manifest. The worker captures the real website and writes independently editable source.</p></section>${conversionPanel()}<section class="convert-steps"><article><span>01 / CAPTURE</span><h3>Bring the published site.</h3><p>Choose page coverage and confirm permission to export.</p></article><article><span>02 / REVIEW</span><h3>See what survived.</h3><p>Inspect responsive layouts, source files and specific warnings.</p></article><article><span>03 / KEEP BUILDING</span><h3>Edit. Export. Own it.</h3><p>Change the content, regenerate and download the real files.</p></article></section>`; }
function jobCard(job) {
    let visual = '';
    if (job.status === 'completed' && job.report) {
        const c = job.report.comparisons.find(c => c.page === 'p0' && c.width === 1440);
        if (c)
            visual = `<img src="${evidenceURL(job, c.export)}" alt="Actual exported page preview" loading="lazy">`;
    }
    return `<button class="job-card" data-job="${job.id}"><div class="job-image">${visual || `<span>${icon('layers', 35)}</span>`}<span class="job-image-badge">${job.request.demo ? 'TEST FIXTURE' : 'WEBSITE EXPORT'}</span></div><div class="job-info"><div><h3>${esc(title(job))}</h3><span>${job.request.demo ? 'Original, authorised sample' : esc(job.request.url.replace(/^https?:\/\//, ''))}</span></div>${icon('up', 17)}</div><div class="job-meta">${statusBadge(job)}<span>${relativeDate(job.created)}</span></div></button>`;
}
function history() { const items = state.jobs.filter(j => (state.filterStatus === 'all' || j.status === state.filterStatus) && (title(j) + ' ' + j.request.url).toLowerCase().includes(state.historyFilter.toLowerCase())); return `<div class="page-heading"><div><div class="eyebrow">YOUR WORK, MOVING FORWARD</div><h1>Your projects<span class="count-heading">${state.jobs.length}</span></h1><p>Every export, its source and the evidence behind it.</p></div><button class="primary" data-view="convert">${icon('plus', 17)}New conversion</button></div><div class="history-toolbar"><div class="filter-input">${icon('search', 16)}<input id="history-search" placeholder="Find a project or website…" value="${esc(state.historyFilter)}"></div><select id="status-filter" aria-label="Project status">${[['all', 'All projects'], ['completed', 'Completed'], ['running', 'Running'], ['queued', 'Queued'], ['failed', 'Failed'], ['cancelled', 'Cancelled']].map(([v, t]) => `<option value="${v}" ${state.filterStatus === v ? 'selected' : ''}>${t}</option>`).join('')}</select><span class="subtle">${items.length} ${items.length === 1 ? 'conversion' : 'conversions'}</span></div>${items.length ? `<div class="history-grid">${items.map(jobCard).join('')}</div>` : `<div class="empty-state">${icon('layers', 38)}<h2>${state.historyFilter ? 'No matching projects' : 'A clean slate. A good start.'}</h2><p>${state.historyFilter ? 'Try another project name.' : 'Your conversions will appear here, with their source and verification reports.'}</p><button class="secondary" id="run-demo">${icon('play', 14)}Try the sample website</button></div>`}`; }
function project() { const job = state.job; const r = job.report; return `<div class="project-heading"><div><button class="back-button" data-view="history">${icon('back', 14)}All conversions</button><h1>${esc(title(job))}</h1><div class="project-subtitle">${icon('globe', 14)}<span>${job.request.demo ? 'Forma · Original Frameport test fixture' : esc(job.request.url)}</span><span class="dot-separator">·</span><span>Revision ${job.revision}</span>${statusBadge(job)}</div></div><div class="project-actions">${job.status === 'completed' ? `<button class="secondary" id="download-html">${icon('code', 16)}HTML</button><button class="primary" id="download-react">${icon('download', 16)}Export React</button>` : job.status === 'running' || job.status === 'queued' ? `<button class="secondary" id="cancel-job">${icon('close', 15)}Cancel</button>` : `<button class="primary" id="retry-job">${icon('refresh', 16)}Try again</button>`}</div></div><div class="project-tools"><button id="rename-project">Rename project</button><button id="copy-project-link">Copy project link ↗</button><button id="delete-project" ${['running', 'queued'].includes(job.status) ? 'disabled' : ''}>Delete</button><span>Saved ${relativeDate(job.updated)} · Revision ${job.revision}</span></div>${job.status === 'completed' && r ? completedProject(job, r) : progressProject(job)}`; }
function progressProject(job) { const failed = ['failed', 'cancelled'].includes(job.status); const stages = ['Inspect', 'Capture', 'Extract', 'Generate', 'Verify', 'Package']; const index = stages.indexOf(job.stage); return `<div class="progress-card"><div class="progress-symbol ${failed ? 'failed' : ''}">${icon(failed ? 'warning' : 'layers', 28)}</div><span class="eyebrow">${failed ? 'NOT MARKED AS SUCCESSFUL' : 'A NEW BEGINNING, IN PROGRESS'}</span><h2>${failed ? (job.status === 'cancelled' ? 'Conversion cancelled.' : 'This export needs another look.') : 'Making your design independently yours.'}</h2><p>${failed ? esc(job.error) : 'Capturing the real site, writing editable source and comparing the result.'}</p>${failed ? '' : `<div class="progress-track"><span style="width:${job.progress}%"></span></div><div class="progress-label"><span>${esc(job.stage)}</span><strong>${job.progress}%</strong></div>`}<div class="stage-grid">${stages.map((s, i) => `<div class="${i < index ? 'done' : i === index ? 'current' : ''}"><span>${i < index ? icon('check', 13) : i + 1}</span>${s}</div>`).join('')}</div><div class="event-log" aria-live="polite">${job.events.slice(-6).map(e => `<div><time>${new Date(e.time * 1000).toLocaleTimeString('en-GB')}</time><span>${esc(e.message)}</span></div>`).join('')}</div>${failed ? '<p class="subtle">No completed export is available. Retry with one page, or check your worker’s network and browser configuration.</p>' : ''}</div>`; }
function completedProject(job, r) { return `<div class="result-stats"><div><span>Pages captured</span><strong>${r.pages.length}<small>of ${job.request.max_pages} maximum</small></strong></div><div><span>Editable components</span><strong>${r.components.length}<small>React + TypeScript</small></strong></div><div><span>Packaged assets</span><strong>${r.assets}<small>with provenance</small></strong></div><div><span>Visual checks</span><strong>${r.comparisons.filter(c => c.passed).length}<small>/ ${r.comparisons.length} passed</small></strong></div></div><div class="project-workbench"><div class="workbench-tabs"><div>${[['preview', 'split', 'Preview'], ['source', 'code', 'Source code'], ['content', 'edit', 'Edit content'], ['report', 'shield', 'Verification'], ['export', 'download', 'Export']].map(([id, ico, label]) => `<button data-tab="${id}" class="${state.tab === id ? 'selected' : ''}">${icon(ico, 16)}${label}${id === 'report' ? `<span class="tab-count">${r.issues.filter(i => i.severity !== 'info').length}</span>` : ''}</button>`).join('')}</div><span class="build-status">${icon('info', 13)}React build not yet verified</span></div>${state.tab === 'preview' ? previewPanel(job, r) : state.tab === 'source' ? sourcePanel() : state.tab === 'content' ? contentPanel() : state.tab === 'export' ? exportView(job) : reportPanel(job, r)}</div>`; }
function evidenceURL(job, name) { return offline ? offline.evidence[name] || '' : `/evidence/${job.id}/${job.ticket}/${name}`; }
function previewPanel(job, r) {
    const comparison = r.comparisons.find(c => c.width === state.width && c.page === state.page) || r.comparisons[0];
    const page = r.pages.find(p => p.key === state.page) || r.pages[0];
    const liveURL = `/preview/${job.id}/${job.ticket}/${page.route === '/' ? 'index.html' : page.route.slice(1) + 'index.html'}`;
    return `<div class="preview-toolbar"><div class="page-select">${icon('file', 15)}<select id="page-select" aria-label="Page">${r.pages.map(p => `<option value="${p.key}" ${p.key === state.page ? 'selected' : ''}>${esc(p.route)}</option>`).join('')}</select></div><div class="viewport-buttons">${[[1440, 'monitor'], [768, 'tablet'], [390, 'phone']].map(([w, i]) => `<button data-width="${w}" class="${state.width === w ? 'selected' : ''}" title="${w}px viewport" aria-label="${w}px viewport">${icon(String(i), 16)}</button>`).join('')}<span>${state.width}px</span></div><div class="preview-modes"><select id="preview-mode" aria-label="Preview mode"><option value="compare" ${state.mode === 'compare' ? 'selected' : ''}>Compare</option><option value="export" ${state.mode === 'export' ? 'selected' : ''}>Exported page</option><option value="diff" ${state.mode === 'diff' ? 'selected' : ''}>Difference map</option>${offline ? '' : '<option value="live" ' + (state.mode === 'live' ? 'selected' : '') + '>Interactive preview</option>'}</select><button class="text-button" id="zoom-button">${state.zoom ? '100%' : 'Fit'}</button></div></div>${state.mode === 'compare' ? `<div class="compare-control"><span>Original</span><input id="compare-range" type="range" min="0" max="100" value="${state.split}" aria-label="Compare original and exported website"><span>Exported HTML</span></div>` : ''}<div class="preview-stage ${state.mode === 'live' ? 'is-live' : ''}"><div class="preview-canvas ${state.zoom ? 'natural' : ''}" style="width:${state.width}px">${state.mode === 'live' ? `<iframe sandbox="allow-scripts" title="Sandboxed exported website" src="${liveURL}" style="width:${state.width}px;height:850px"></iframe>` : state.mode === 'compare' ? `<img class="source-image" src="${evidenceURL(job, comparison.source)}" alt="Original captured website"><img class="export-image" src="${evidenceURL(job, comparison.export)}" alt="Independently exported HTML" style="clip-path:inset(0 0 0 ${state.split}%)"><div class="compare-line" style="left:${state.split}%"><span>${icon('split', 14)}</span></div><div class="canvas-tags"><span>ORIGINAL</span><span>EXPORTED HTML</span></div>` : `<img src="${evidenceURL(job, state.mode === 'diff' ? comparison.diff : comparison.export)}" alt="${state.mode === 'diff' ? 'Changed pixels highlighted in pink' : 'Actual exported website'}">`}</div></div><div class="preview-foot"><span class="${comparison.passed ? 'good' : 'review'}">${icon(comparison.passed ? 'check' : 'warning', 14)}${comparison.matchedPixels.toFixed(2)}% matched pixels <b>·</b> ${comparison.width}px</span><span>${state.mode === 'live' ? 'Sandboxed. Source scripts and form submission are disabled.' : 'Captured HTML states only. Pink in the difference map marks changed pixels.'}</span></div>`;
}
function sourcePanel() { return `<div class="source-layout"><aside class="file-tree"><div class="file-tree-heading">${icon('folder', 15)}<select id="source-target" aria-label="Source target"><option value="react" ${state.sourceTarget === 'react' ? 'selected' : ''}>React project</option><option value="html" ${state.sourceTarget === 'html' ? 'selected' : ''}>HTML project</option></select></div><div class="file-list">${state.files.map(f => `<button data-file="${esc(f.path)}" class="${state.file === f.path ? 'selected' : ''}"><span class="file-type ${f.path.endsWith('.tsx') ? 'tsx' : f.path.endsWith('.css') ? 'css' : ''}">${f.path.endsWith('.tsx') ? 'R' : f.path.endsWith('.json') ? '{}' : f.path.endsWith('.css') ? '#' : '◇'}</span><span>${esc(f.path)}</span></button>`).join('')}</div></aside><div class="code-view"><div class="code-heading"><span>${icon('file', 14)}${esc(state.file || 'Select a file')}</span><button class="text-button" id="copy-code">${icon('copy', 14)}Copy</button></div><div class="code-scroll"><div class="line-numbers">${state.code.split('\n').map((_, i) => i + 1).join('\n')}</div><pre><code>${esc(state.code || 'Choose a source file to inspect its actual generated code.')}</code></pre></div><div class="code-foot">${icon('code', 13)}Real source files. No screenshots embedded as layouts. No dangerouslySetInnerHTML.</div></div></div>`; }
function contentPanel() { return `<div class="content-intro"><div><h3>Small changes. Your own voice.</h3><p>Edit the extracted text, then rebuild both projects. Visual evidence is regenerated against the original.</p></div><button class="primary" id="save-content" ${!state.edits.size ? 'disabled' : ''}>${icon('refresh', 15)}Rebuild${state.edits.size ? ' ' + state.edits.size + ' edits' : ''}</button></div><div class="content-fields">${state.contents.length ? state.contents.slice(0, 200).map(c => `<label class="content-field"><span>${esc(c.id)}${state.edits.has(c.id) ? '<b>EDITED</b>' : ''}</span><textarea data-content="${esc(c.id)}" rows="${c.text.length > 150 ? 3 : c.text.length > 70 ? 2 : 1}" maxlength="5000">${esc(state.edits.get(c.id) ?? c.text)}</textarea></label>`).join('') : '<div class="loading-text">Loading extracted content…</div>'}</div><div class="content-note">${icon('info', 14)}Content edits are safely escaped. The downloaded React project stores these fields in <code>src/content/site.json</code>.</div>`; }
function reportPanel(_job, r) { const issues = r.issues.filter(i => i.severity !== 'info'); const matched = 100 * (1 - r.comparisons.reduce((a, c) => a + c.changedPixels, 0) / Math.max(1, r.comparisons.reduce((a, c) => a + c.totalPixels, 0))); return `${r.execution ? `<div class="scope-note evidence-notice">${icon('info', 15)}<span>${esc(r.execution.description)}</span></div>` : ''}<div class="report-header"><span class="report-emblem ${r.visualPassed ? 'passed' : ''}">${icon(r.visualPassed ? 'shield' : 'warning', 28)}</span><div><span class="eyebrow">THE EVIDENCE, WITHOUT THE GUESSWORK</span><h2>${r.visualPassed ? 'The captured HTML passes its visual checks.' : 'Some captured states need a closer look.'}</h2><p>${r.comparisons.length} comparisons across ${r.pages.length} pages. ${matched.toFixed(2)}% matched pixels overall.</p></div><button class="secondary" id="download-report">${icon('download', 15)}Report</button></div><div class="report-scope">${icon('info', 18)}<div><strong>A visual pass is not a universal conversion guarantee.</strong><p>These checks cover rendered HTML at 390, 540, 768, 1024 and 1440px, up to 6,000px down each page. Arbitrary scripts, backend services and the React production build are not verified.</p></div></div><div class="verification-grid"><section><h3>Responsive comparison</h3><div class="matrix"><div class="matrix-row matrix-head"><span>PAGE</span>${r.coverage.widths.map(w => `<span>${w}px</span>`).join('')}</div>${r.pages.map(p => `<div class="matrix-row"><strong>${esc(p.route)}</strong>${r.coverage.widths.map(w => { const c = r.comparisons.find(c => c.page === p.key && c.width === w); return `<button data-inspect="${p.key}:${w}" class="${c?.passed ? 'pass' : 'review'}" title="${c?.matchedPixels.toFixed(2)}% matched pixels">${icon(c?.passed ? 'check' : 'warning', 14)}${c?.matchedPixels.toFixed(1)}%</button>`; }).join('')}</div>`).join('')}</div><div class="matrix-key"><span><i class="pass-key"></i>Within 2% changed pixels</span><span><i class="review-key"></i>Review required</span></div></section><section class="report-details"><h3>What was tested</h3><div>${icon('check', 14)}Independent HTML with external resource requests blocked</div><div>${icon('check', 14)}Local image loading and the initial page states</div><div>${icon('check', 14)}Native disclosures and visible aria-controls adapters</div><div class="not-tested">${icon('info', 14)}React npm install and production build: not run</div></section></div><div class="issues-section"><div class="section-title"><h3>Needs your attention<span class="tab-count">${issues.length}</span></h3><span class="subtle">Nothing hidden behind a success badge.</span></div>${issues.length ? issues.map(i => `<div class="issue-row">${icon('warning', 18)}<div><strong>${esc(i.code.replaceAll('-', ' '))}${i.page ? ` <span>${esc(i.page)}</span>` : ''}</strong><p>${esc(i.message)}</p></div>${(i.count || 1) > 1 ? `<span class="tab-count">×${i.count}</span>` : ''}</div>`).join('') : '<div class="clear-issues">' + icon('check', 18) + 'No additional warnings were detected within this test scope.</div>'}</div>${r.demo ? '<div class="demo-disclosure">' + icon('info', 16) + 'This result comes from Forma, an original Framer-style test fixture. It is not a benchmark of a live, Framer-published website.</div>' : ''}`; }
function docs() { return `<div class="page-heading"><div><div class="eyebrow">A LITTLE CONTEXT GOES A LONG WAY</div><h1>Built to be understood.</h1><p>What Frameport does, how to run it and where the boundaries are.</p></div><span class="badge neutral">${icon('book', 13)}Developer guide · v0.1</span></div><div class="docs-grid"><section class="doc-card"><span class="doc-number">01 / START HERE</span><h2>A real worker.<br>A real export.</h2><p>The included Python worker runs Chromium, captures public pages, collects assets and compiles standalone source. This interface is its control room.</p><div class="terminal"><div><i></i><i></i><i></i><span>Terminal</span></div><pre>python -m venv .venv\nsource .venv/bin/activate\npip install -e '.[dev]'\npython -m playwright install chromium\npython -m frameport.cli</pre></div><p class="subtle">Open <code>http://127.0.0.1:8040</code>. Requires Python 3.11 or later. The full README includes Windows and Docker instructions.</p></section><section class="doc-card"><span class="doc-number">02 / HOW IT WORKS</span><h2>Evidence at<br>every step.</h2><div class="pipeline-list">${[['globe', 'Capture', 'Read the rendered site at five viewport widths.'], ['layers', 'Understand', 'Preserve markup, style rules, assets and page boundaries.'], ['code', 'Generate', 'Write HTML and React with separate component and content files.'], ['shield', 'Verify', 'Render the HTML independently and compare actual pixels.']].map(([i, t, d], n) => `<div><span>${icon(i, 19)}</span><div><strong>${n + 1}. ${t}</strong><p>${d}</p></div></div>`).join('')}</div></section></div><section class="support-card"><div class="section-title"><h2>Clear boundaries make better software.</h2><span class="badge amber">Review before publishing</span></div><div class="support-grid"><div><h3>${icon('check', 16)}Implemented</h3><p>Published URL capture; bounded same-origin crawling; local assets; original responsive CSS; separate React sections; editable text; standalone HTML; visual comparison; native disclosures; cancellation, retries and downloadable evidence.</p></div><div><h3>${icon('info', 16)}Requires separate verification</h3><p>Real Framer-published sites, Framer motion and custom controls, dynamically changing DOM, uncommon CSS, font licences, React dependency installation, clean production builds, and any backend integrations.</p></div><div><h3>${icon('lock', 16)}Not a public SaaS yet</h3><p>This release is for one trusted workspace. Public launch requires isolated workers, network-level egress controls, tenant isolation, authentication, billing, abuse controls and operational review.</p></div></div></section><section class="doc-card bridge-doc"><span class="doc-number">03 / CONNECTED PROJECTS</span><h2>The project bridge</h2><p>A manifest can carry the project name, published address, layer metadata and optional CMS content into a conversion. It does not recover proprietary Framer runtime code. An experimental read-only plugin adapter is included in <code>integrations/framer-plugin</code>; its in-editor integration still needs a genuine Framer test.</p><pre class="manifest-example">${esc(JSON.stringify({ schema: 'frameport.bridge.v1', publishedUrl: 'https://your-site.framer.website', project: { name: 'Your project' }, nodes: [], collections: [] }, null, 2))}</pre><p class="subtle">Only import content and assets you are authorised to export. Manifests stay with your local workspace.</p></section>`; }
let eclipse = null;
let motionPaused = false;
function render() {
    eclipse?.dispose();
    eclipse = null;
    const app = $('#app');
    if (!app)
        return;
    let content;
    if (state.loading)
        content = '<div class="screen-loading" role="status"><span class="busy-marker"></span><h1>Opening your workspace.</h1><p>Loading the saved project and its current revision.</p></div>';
    else if (state.problem)
        content = problemView(state.problem, state.problemKind);
    else
        content = state.view === 'overview' ? overview() : state.view === 'convert' ? convertView() : state.view === 'history' ? history() : state.view === 'docs' ? docs() : state.view === 'settings' ? settingsView(state.health, !state.auth && backendConnected()) : state.view === 'login' ? loginView('', backendConnected()) : state.view === 'project' && state.job ? project() : problemView('This address does not match a page in Frameport.', 'notfound');
    app.innerHTML = shell(content);
    bind();
    const canvas = $('#hero-shader');
    if (canvas) {
        eclipse = mountEclipse(canvas, { paused: motionPaused, onState: ({ motion }) => { const button = $('#motion-toggle'); if (!button)
                return; button.disabled = motion === 'unavailable' || motion === 'reduced'; button.textContent = motion === 'unavailable' ? 'Static artwork' : motion === 'reduced' ? 'Reduced motion' : motion === 'paused' ? 'Play motion' : 'Pause motion'; button.setAttribute('aria-pressed', String(motion === 'paused')); button.setAttribute('aria-label', motion === 'paused' ? 'Play background animation' : 'Pause background animation'); } });
    }
}
window.addEventListener('pagehide', () => { eclipse?.dispose(); eclipse = null; });
window.addEventListener('pageshow', event => { if (event.persisted)
    render(); });
async function loadJob(id) { await navigate(projectPath(id)); }
function pollJob() {
    clearTimeout(state.poll);
    if (!state.job || !['queued', 'running'].includes(state.job.status) || state.view !== 'project')
        return;
    const id = state.job.id, generation = routeGeneration;
    state.poll = window.setTimeout(async () => {
        try {
            const job = await api(`/api/jobs/${id}`);
            if (generation !== routeGeneration || state.job?.id !== id)
                return;
            state.job = job;
            upsertJob(job);
            if (job.status === 'completed') {
                state.files = [];
                state.code = '';
                state.contents = [];
                render();
                if (['source', 'content'].includes(state.tab))
                    await changeTab(state.tab, false);
            }
            else
                render();
            pollJob();
        }
        catch (e) {
            if (generation === routeGeneration) {
                toast(e.message);
                state.poll = window.setTimeout(pollJob, 3000);
            }
        }
    }, document.hidden ? 3000 : 1100);
}
async function submitJob(payload) {
    if (submitting)
        return;
    if (!offline && (!state.worker || state.auth)) {
        await navigate(state.auth ? '/login' : '/settings');
        return;
    }
    submitting = true;
    const button = $('.convert-button');
    if (button)
        button.disabled = true;
    try {
        const job = await api('/api/jobs', { method: 'POST', headers: { 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify(payload) });
        upsertJob(job);
        state.edits.clear();
        await navigate(projectPath(job.id));
    }
    catch (e) {
        toast(e.message);
        if (button)
            button.disabled = false;
    }
    finally {
        submitting = false;
    }
}
async function runDemo() { if (offline) {
    await loadJob(offline.job.id);
    return;
} await submitJob({ demo: true, permission: true, name: 'Forma Studio', max_pages: 3, crawl: true, format: 'both' }); }
async function changeTab(tab, push = true) {
    if (!state.job)
        return;
    const id = state.job.id, revision = state.job.revision;
    state.tab = tab;
    if (push)
        writeLocation(projectPath(id, tab));
    const generation = routeGeneration;
    render();
    try {
        if (tab === 'source') {
            const target = state.sourceTarget;
            const files = await api(`/api/jobs/${id}/files?target=${target}`);
            if (generation !== routeGeneration || state.tab !== tab || state.job?.id !== id || state.job.revision !== revision || state.sourceTarget !== target)
                return;
            state.files = files;
            if (!files.some(f => f.path === state.file))
                state.file = files.find(f => f.path.endsWith('Hero.tsx'))?.path || files.find(f => f.path.endsWith('App.tsx'))?.path || files[0]?.path || '';
            if (state.file)
                await loadFile(state.file);
            else
                render();
        }
        if (tab === 'content') {
            const contents = await api(`/api/jobs/${id}/content`);
            if (generation !== routeGeneration || state.tab !== tab || state.job?.id !== id || state.job.revision !== revision)
                return;
            state.contents = contents;
            render();
        }
    }
    catch (e) {
        if (generation === routeGeneration)
            toast(e.message);
    }
}
async function loadFile(path) {
    if (!state.job)
        return;
    const request = ++fileGeneration, id = state.job.id, revision = state.job.revision, target = state.sourceTarget;
    try {
        const file = await api(`/api/jobs/${id}/file?target=${target}&path=${encodeURIComponent(path)}`);
        if (request !== fileGeneration || state.job?.id !== id || state.job.revision !== revision || state.tab !== 'source' || state.sourceTarget !== target)
            return;
        state.file = path;
        state.code = file.content;
        syncQuery();
        render();
    }
    catch (e) {
        if (request === fileGeneration)
            toast(e.message);
    }
}
async function download(target) {
    try {
        let url;
        let name;
        if (offline) {
            url = target === 'report' ? 'data:application/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(offline.job.report, null, 2)) : offline.downloads[target];
            name = target === 'report' ? 'frameport-verification.json' : `frameport-forma-${target}.zip`;
        }
        else if (target !== 'report') {
            const links = await api(`/api/jobs/${state.job.id}/export-links`);
            const a = document.createElement('a');
            a.href = links[target].url;
            a.rel = 'noreferrer';
            a.download = `frameport-${target}.zip`;
            a.click();
            toast('Your download is starting.');
            return;
        }
        else {
            const path = target === 'report' ? `/api/jobs/${state.job.id}/report` : `/api/jobs/${state.job.id}/download/${target}`;
            const response = await fetch(path, { headers: state.key ? { Authorization: `Bearer ${state.key}` } : {} });
            if (!response.ok)
                throw new Error('Export is unavailable. Reload this conversion.');
            url = URL.createObjectURL(await response.blob());
            name = target === 'report' ? 'frameport-verification.json' : `frameport-${target}-${state.job.id.slice(0, 8)}.zip`;
        }
        const a = document.createElement('a');
        a.href = url;
        a.download = name;
        a.click();
        if (url.startsWith('blob:'))
            setTimeout(() => URL.revokeObjectURL(url), 60000);
        toast('Your export is ready.');
    }
    catch (e) {
        toast(e.message);
    }
}
function showAccess() { if (!offline && !backendConnected()) {
    void navigate('/settings');
    return;
} const root = $('#modal-root'); if (!root)
    return; root.innerHTML = `<div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="access-title"><button class="icon-button modal-close" id="close-modal" aria-label="Close">${icon('close', 18)}</button><span class="modal-icon">${icon('lock', 26)}</span><h2 id="access-title">Your workspace.<br>Your access.</h2><p>${offline ? 'This is a self-contained preview of the real application. Run the included worker for live conversions.' : 'Enter the FRAMEPORT_API_KEY configured on your worker. It is exchanged for an HTTP-only session. Your sign-in survives refreshes.'}</p>${offline ? '<button class="primary" id="modal-docs">Read setup instructions</button>' : '<form id="access-form"><label>Worker access key<input type="password" id="access-key" autocomplete="off" required></label><button class="primary" type="submit">Connect workspace ' + icon('arrow', 15) + '</button></form>'}</section></div>`; $('#close-modal')?.addEventListener('click', () => root.innerHTML = ''); $('#modal-docs')?.addEventListener('click', () => { void navigate('/docs'); }); $('#access-key')?.focus(); $('#access-form')?.addEventListener('submit', async (e) => { e.preventDefault(); const key = $('#access-key').value; try {
    await api('/api/session', { method: 'POST', body: JSON.stringify({ key }) });
    state.key = '';
    state.auth = false;
    await refreshHealth();
    await applyRoute(activePath);
    toast('Workspace connected.');
}
catch (e) {
    toast(e.message);
} }); }
function bind() {
    bindPlatform();
    $('#start-converting')?.addEventListener('click', () => { $('#convert')?.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' }); $('#url')?.focus({ preventScroll: true }); });
    $('#hero-demo')?.addEventListener('click', runDemo);
    $('#motion-toggle')?.addEventListener('click', () => { motionPaused = !motionPaused; eclipse?.setPaused(motionPaused); });
    $$('[data-view]').forEach(el => el.addEventListener('click', e => { e.preventDefault(); void navigate(viewPath(el.getAttribute('data-view'))); }));
    $$('[data-job]').forEach(el => el.addEventListener('click', () => loadJob(el.getAttribute('data-job'))));
    $('#run-demo')?.addEventListener('click', runDemo);
    $('#find-button')?.addEventListener('click', async () => { await navigate('/projects'); $('#history-search')?.focus(); });
    $('#workspace-button')?.addEventListener('click', showAccess);
    $('#profile-button')?.addEventListener('click', showAccess);
    $('#url-tab')?.addEventListener('click', () => { state.formTab = 'url'; render(); });
    $('#bridge-tab')?.addEventListener('click', () => { state.formTab = 'bridge'; render(); });
    $('#bridge-help')?.addEventListener('click', () => { void navigate('/docs'); });
    $('#options-toggle')?.addEventListener('click', () => { const el = $('#export-options'); if (el) {
        el.hidden = !el.hidden;
        $('#options-toggle')?.setAttribute('aria-expanded', String(!el.hidden));
    } });
    $('#conversion-form')?.addEventListener('submit', async (e) => { e.preventDefault(); await submitJob({ url: $('#url').value, name: $('#project-name')?.value || '', permission: $('#permission').checked, max_pages: Number($('#max-pages')?.value || 3), crawl: $('#crawl')?.checked ?? true, format: 'both' }); });
    $('#manifest-input')?.addEventListener('change', async (e) => { try {
        const file = e.target.files?.[0];
        if (!file)
            return;
        if (file.size > 1_000_000)
            throw new Error('Manifest must be smaller than 1 MB.');
        const manifest = JSON.parse(await file.text());
        if (manifest.schema !== 'frameport.bridge.v1' || !manifest.publishedUrl)
            throw new Error('Choose a valid Frameport bridge manifest with a published URL.');
        if (!confirm('Confirm that you own this project or have permission to export its design and included content.'))
            return;
        await submitJob({ url: manifest.publishedUrl, name: manifest.project?.name || '', permission: true, max_pages: 3, crawl: true, format: 'both', bridge: manifest });
    }
    catch (e) {
        toast(e.message);
    } });
    $('#history-search')?.addEventListener('input', e => { const input = e.target; const pos = input.selectionStart; state.historyFilter = input.value; render(); const next = $('#history-search'); next?.focus(); next?.setSelectionRange(pos, pos); });
    $$('[data-tab]').forEach(el => el.addEventListener('click', () => changeTab(el.getAttribute('data-tab'))));
    $$('[data-width]').forEach(el => el.addEventListener('click', () => { state.width = Number(el.getAttribute('data-width')); syncQuery(); render(); }));
    $('#page-select')?.addEventListener('change', e => { state.page = e.target.value; syncQuery(); render(); });
    $('#preview-mode')?.addEventListener('change', e => { state.mode = e.target.value; render(); });
    $('#compare-range')?.addEventListener('input', e => { state.split = Number(e.target.value); const im = $('.export-image'); const ln = $('.compare-line'); if (im)
        im.style.clipPath = `inset(0 0 0 ${state.split}%)`; if (ln)
        ln.style.left = `${state.split}%`; });
    $('#zoom-button')?.addEventListener('click', () => { state.zoom = !state.zoom; render(); });
    $('#download-react')?.addEventListener('click', () => download('react'));
    $('#download-html')?.addEventListener('click', () => download('html'));
    $('#download-report')?.addEventListener('click', () => download('report'));
    $('#cancel-job')?.addEventListener('click', async () => { try {
        state.job = await api(`/api/jobs/${state.job.id}/cancel`, { method: 'POST', body: '{}' });
        render();
        pollJob();
    }
    catch (e) {
        toast(e.message);
    } });
    $('#retry-job')?.addEventListener('click', async () => { try {
        const j = await api(`/api/jobs/${state.job.id}/retry`, { method: 'POST', body: '{}' });
        upsertJob(j);
        await navigate(projectPath(j.id));
    }
    catch (e) {
        toast(e.message);
    } });
    $$('[data-file]').forEach(el => el.addEventListener('click', () => loadFile(el.getAttribute('data-file'))));
    $('#source-target')?.addEventListener('change', e => { state.sourceTarget = e.target.value; state.file = ''; changeTab('source'); });
    $('#copy-code')?.addEventListener('click', async () => { try {
        await navigator.clipboard.writeText(state.code);
        toast('Source code copied.');
    }
    catch {
        toast('Clipboard access is unavailable. Select and copy the source directly.');
    } });
    $$('[data-content]').forEach(el => el.addEventListener('input', () => { const id = el.dataset.content; const original = state.contents.find(c => c.id === id)?.text; if (el.value === original)
        state.edits.delete(id);
    else
        state.edits.set(id, el.value); const btn = $('#save-content'); if (btn) {
        btn.disabled = !state.edits.size;
        btn.innerHTML = icon('refresh', 15) + `Rebuild${state.edits.size ? ' ' + state.edits.size + ' edits' : ''}`;
    } }));
    $('#save-content')?.addEventListener('click', async () => { const button = $('#save-content'); if (button)
        button.disabled = true; try {
        state.job = await api(`/api/jobs/${state.job.id}/edits`, { method: 'POST', body: JSON.stringify({ expected_revision: state.job.revision, patches: Array.from(state.edits).map(([id, text]) => ({ id, text })) }) });
        state.edits.clear();
        render();
        pollJob();
    }
    catch (e) {
        toast(e.message);
        if (button)
            button.disabled = false;
    } });
    $$('[data-inspect]').forEach(el => el.addEventListener('click', () => { const [p, w] = el.getAttribute('data-inspect').split(':'); state.page = p; state.width = Number(w); state.mode = 'diff'; state.tab = 'preview'; writeLocation(projectPath(state.job.id)); syncQuery(); render(); }));
}
function backendConnected() { return !!offline || ['local-disk', 'persistent-volume'].includes(state.health.storage || ''); }
function upsertJob(job) { const index = state.jobs.findIndex(j => j.id === job.id); if (index < 0)
    state.jobs.unshift(job);
else
    state.jobs[index] = job; }
async function refreshHealth() {
    if (offline)
        return;
    try {
        state.health = await api('/api/health');
        state.worker = state.health.canConvert === true;
        state.auth = state.health.authRequired;
        if (backendConnected()) {
            const session = await api('/api/session');
            state.auth = !session.authenticated;
            if (!state.auth)
                state.jobs = await api('/api/jobs');
        }
    }
    catch {
        state.worker = false;
        state.health = { worker: 'offline', canConvert: false, authRequired: false, storage: 'not-connected', message: 'The workspace service is not responding.' };
    }
}
function writeLocation(path, replace = false) {
    activePath = path;
    if (!offline && /^https?:$/.test(location.protocol))
        window.history[replace ? 'replaceState' : 'pushState']({}, '', path);
}
function syncQuery() {
    if (!state.job || state.view !== 'project' || offline)
        return;
    const url = new URL(projectPath(state.job.id, state.tab), location.href);
    if (state.page !== 'p0')
        url.searchParams.set('page', state.page);
    if (state.width !== 1440)
        url.searchParams.set('width', String(state.width));
    if (state.tab === 'source' && state.file)
        url.searchParams.set('file', state.file);
    if (state.sourceTarget !== 'react')
        url.searchParams.set('target', state.sourceTarget);
    writeLocation(url.pathname + url.search, true);
}
async function navigate(path, replace = false) {
    const route = parseRoute(path);
    if (state.edits.size && route.id !== state.job?.id && !confirm('Leave this project and discard unsaved text edits?'))
        return;
    if (route.id !== state.job?.id)
        state.edits.clear();
    writeLocation(path, replace);
    await applyRoute(path);
    window.scrollTo(0, 0);
}
async function applyRoute(path) {
    const generation = ++routeGeneration;
    ++fileGeneration;
    clearTimeout(state.poll);
    const route = parseRoute(path);
    activePath = path;
    state.problem = '';
    state.loading = false;
    state.view = route.view;
    state.tab = route.tab;
    state.file = route.file;
    state.sourceTarget = route.target;
    state.page = route.page;
    state.width = route.width;
    if (['project', 'history'].includes(route.view)) {
        if (!backendConnected()) {
            state.problem = 'The persistent workspace service is not connected. No temporary or simulated projects are being shown.';
            state.problemKind = 'offline';
            render();
            return;
        }
        if (state.auth) {
            state.view = 'login';
            render();
            return;
        }
        state.loading = true;
        render();
        try {
            if (route.view === 'history')
                state.jobs = await api('/api/jobs');
            else {
                const job = await api(`/api/jobs/${route.id}`);
                if (generation !== routeGeneration)
                    return;
                state.job = job;
                upsertJob(job);
                state.files = [];
                state.code = '';
                state.contents = [];
                if (job.report && !job.report.pages.some(p => p.key === state.page))
                    state.page = job.report.pages[0]?.key || 'p0';
            }
        }
        catch (e) {
            if (generation !== routeGeneration)
                return;
            if (e instanceof ApiError && e.status === 401) {
                state.auth = true;
                state.view = 'login';
            }
            else {
                state.problem = e.message;
                state.problemKind = e instanceof ApiError && e.status === 404 ? 'notfound' : 'offline';
            }
        }
    }
    if (generation !== routeGeneration)
        return;
    state.loading = false;
    render();
    if (route.view === 'project' && state.job && !state.problem && state.view !== 'login') {
        if (state.job.status === 'completed' && ['source', 'content'].includes(state.tab))
            await changeTab(state.tab, false);
        else
            pollJob();
    }
    const pageTitle = state.view === 'project' && state.job ? title(state.job) : { overview: 'Your design. Your code.', convert: 'New conversion', history: 'Projects', docs: 'Documentation', settings: 'Workspace settings', login: 'Sign in', notfound: 'Page not found' }[state.view];
    document.title = `${pageTitle || 'Studio'} · Frameport`;
}
function bindPlatform() {
    $$('[data-route]').forEach(el => el.addEventListener('click', e => { if (e instanceof MouseEvent && (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0))
        return; e.preventDefault(); void navigate(el.getAttribute('data-route')); }));
    $('#refresh-health')?.addEventListener('click', async () => { await refreshHealth(); render(); });
    $('#retry-route')?.addEventListener('click', async () => { await refreshHealth(); await applyRoute(activePath); });
    $('#connect-workspace')?.addEventListener('click', () => navigate('/login'));
    $('#logout-workspace')?.addEventListener('click', async () => { try {
        await api('/api/session', { method: 'DELETE', body: '{}' });
        state.key = '';
        state.auth = true;
        state.jobs = [];
        state.job = null;
        await navigate('/login');
    }
    catch (e) {
        toast(e.message);
    } });
    $('#platform-login')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const input = $('#login-key'), button = $('#platform-login button');
        button.disabled = true;
        try {
            await api('/api/session', { method: 'POST', body: JSON.stringify({ key: input.value }) });
            input.value = '';
            state.key = '';
            state.auth = false;
            await refreshHealth();
            const returnPath = activePath.startsWith('/projects/') ? activePath : safeReturnPath(new URL(location.href).searchParams.get('next') || '/projects');
            await navigate(returnPath, true);
        }
        catch (error) {
            const message = $('#platform-login .form-error');
            if (message)
                message.textContent = error.message;
            button.disabled = false;
        }
    });
    $('#status-filter')?.addEventListener('change', e => { state.filterStatus = e.target.value; render(); });
    $$('[data-export]').forEach(el => el.addEventListener('click', () => download(el.getAttribute('data-export'))));
    $('#copy-project-link')?.addEventListener('click', async () => { try {
        await navigator.clipboard.writeText(new URL(projectPath(state.job.id, state.tab), location.href).href);
        toast('Project link copied. Sign-in is still required.');
    }
    catch {
        toast('Copy this project’s address from your browser.');
    } });
    $('#rename-project')?.addEventListener('click', () => {
        const root = $('#modal-root');
        if (!root || !state.job)
            return;
        root.innerHTML = `<div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="rename-title"><h2 id="rename-title">Name this project.</h2><form id="rename-form"><input id="rename-input" aria-label="Project name" maxlength="80" value="${esc(title(state.job))}" required><button class="primary">Save name</button><button type="button" id="cancel-rename" class="secondary">Cancel</button></form></section></div>`;
        $('#rename-input')?.focus();
        $('#cancel-rename')?.addEventListener('click', () => root.innerHTML = '');
        $('#rename-form')?.addEventListener('submit', async (e) => { e.preventDefault(); try {
            const job = await api(`/api/jobs/${state.job.id}`, { method: 'PATCH', body: JSON.stringify({ name: $('#rename-input').value }) });
            state.job = job;
            upsertJob(job);
            render();
        }
        catch (error) {
            toast(error.message);
        } });
    });
    $('#delete-project')?.addEventListener('click', async () => {
        if (!state.job || !confirm('Permanently delete this project, its files and verification evidence?'))
            return;
        try {
            await api(`/api/jobs/${state.job.id}`, { method: 'DELETE', body: '{}' });
            state.jobs = state.jobs.filter(j => j.id !== state.job.id);
            state.job = null;
            state.edits.clear();
            await navigate('/projects');
            toast('Project deleted.');
        }
        catch (e) {
            toast(e.message);
        }
    });
    if (!offline && (!state.worker || state.auth)) {
        for (const selector of ['.convert-button', '#run-demo']) {
            const button = $(selector);
            if (button) {
                button.disabled = true;
                button.title = state.auth ? 'Sign in to convert.' : 'Connect the browser service in Workspace settings.';
            }
        }
    }
}
window.addEventListener('popstate', () => { void applyRoute(location.pathname + location.search); });
window.addEventListener('beforeunload', e => { if (state.edits.size) {
    e.preventDefault();
    e.returnValue = '';
} });
document.addEventListener('keydown', e => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    void navigate('/projects').then(() => $('#history-search')?.focus());
} if (e.key === 'Escape') {
    const root = $('#modal-root');
    if (root)
        root.innerHTML = '';
} });
void boot();
