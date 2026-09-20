"""Stateless Vercel web gateway. Never creates SQLite, jobs or browser workers.

Only an operator-configured upstream is contacted. Browser-provided URLs cannot
select a proxy target. Missing infrastructure fails explicitly, without accepting
jobs that would disappear on the next serverless invocation.
"""
from __future__ import annotations
from contextlib import asynccontextmanager
import os
from urllib.parse import urlsplit
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.background import BackgroundTask
from starlette.staticfiles import StaticFiles
from .config import ROOT
from .web_routes import APP_CSP, install_documents

MAX_BODY = 1_200_000
HOP_HEADERS = {'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
               'te', 'trailer', 'transfer-encoding', 'upgrade', 'content-length', 'content-encoding'}


def normalise_origin(raw: str, *, local_test: bool = False) -> str:
    raw = raw.strip().rstrip('/')
    if not raw:
        return ''
    u = urlsplit(raw)
    allowed_local = local_test and u.scheme == 'http' and u.hostname == '127.0.0.1'
    if (not allowed_local and u.scheme != 'https') or not u.hostname or u.username or u.password or u.query or u.fragment or u.path:
        raise ValueError('FRAMEPORT_WORKER_ORIGIN must be an HTTPS origin, without a path or credentials.')
    if not allowed_local and (u.port not in (None, 443) or '.' not in u.hostname or ':' in u.hostname):
        raise ValueError('The worker origin must use a public HTTPS hostname.')
    if not allowed_local:
        import ipaddress
        try:
            ip = ipaddress.ip_address(u.hostname)
            if not ip.is_global:
                raise ValueError('Private worker addresses are not supported by the public gateway.')
        except ValueError as error:
            if 'Private' in str(error):
                raise
        if u.hostname.endswith(('.localhost', '.local', '.internal', '.lan')):
            raise ValueError('Local worker domains are not supported by the public gateway.')
    return raw


def unavailable(reason='worker-unconfigured', status=503):
    return JSONResponse({'detail': 'The conversion service is not connected. No job has been queued.',
                         'code': reason, 'setupUrl': '/settings'}, status_code=status,
                        headers={'Cache-Control': 'no-store'})


def create_gateway(origin: str | None = None, *, transport=None, local_test=False):
    upstream = normalise_origin(origin if origin is not None else os.getenv('FRAMEPORT_WORKER_ORIGIN', ''), local_test=local_test)
    # Reused for this process; no lifespan-dependent initialisation on Vercel.
    client = httpx.AsyncClient(timeout=httpx.Timeout(30, connect=8), follow_redirects=False,
                               transport=transport, headers={'Accept-Encoding': 'identity'})
    @asynccontextmanager
    async def lifespan(app):
        yield
        await client.aclose()
    app = FastAPI(title='Frameport gateway', version='0.2.0', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.worker_origin = upstream
    @app.middleware('http')
    async def secure(request: Request, call_next):
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin_header = request.headers.get('origin')
            expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
            public = os.getenv('FRAMEPORT_PUBLIC_ORIGIN', '').rstrip('/')
            if origin_header and origin_header not in {expected, public}:
                return JSONResponse({'detail': 'Cross-origin writes are not allowed.'}, status_code=403)
            if request.headers.get('content-type', '').split(';')[0] != 'application/json':
                return JSONResponse({'detail': 'Use application/json.'}, status_code=415)
            parts, total = [], 0
            async for chunk in request.stream():
                total += len(chunk)
                if total > MAX_BODY:
                    return JSONResponse({'detail': 'Request body is too large.'}, status_code=413)
                parts.append(chunk)
            request._body = b''.join(parts)
        response = await call_next(request)
        response.headers.setdefault('Content-Security-Policy', APP_CSP)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        if not request.url.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/api/health')
    async def health():
        base = dict(name='Frameport', version='0.2.0', deployment='gateway', worker='unconfigured',
                    authRequired=False, storage='not-connected', canConvert=False, publicService=False)
        if not upstream:
            return base | {'message': 'Connect the persistent conversion service to activate your workspace.'}
        try:
            result = await client.get(upstream + '/api/health')
            result.raise_for_status()
            payload = result.json()
            if not isinstance(payload, dict):
                raise ValueError('Invalid worker health response')
            # Do not infer readiness merely from HTTP 200 or trust arbitrary fields.
            ready = payload.get('canConvert') is True and payload.get('worker') == 'available'
            return base | {k: payload[k] for k in ('worker', 'authRequired', 'storage', 'message', 'queueDepth', 'activeJobs') if k in payload} | {'canConvert': ready}
        except (httpx.HTTPError, ValueError):
            return base | {'worker': 'offline', 'message': 'The configured conversion service is not responding.'}

    @app.get('/api/ready')
    async def ready():
        result = await health()
        return JSONResponse(result, status_code=200 if result['canConvert'] else 503)

    @app.api_route('/api/{path:path}', methods=['GET', 'HEAD', 'POST', 'PATCH', 'DELETE'])
    @app.api_route('/preview/{path:path}', methods=['GET', 'HEAD'])
    @app.api_route('/evidence/{path:path}', methods=['GET', 'HEAD'])
    @app.api_route('/download/{path:path}', methods=['GET', 'HEAD'])
    async def proxy(request: Request, path: str):
        if not upstream:
            return unavailable()
        # Encoded traversal must not escape the expected upstream route family.
        import urllib.parse
        decoded = urllib.parse.unquote(request.url.path)
        if '\\' in decoded or any(p in ('.', '..') for p in decoded.split('/')):
            return unavailable('invalid-path', 400)
        headers = {k: v for k, v in request.headers.items() if k.lower() in {
            'accept', 'authorization', 'content-type', 'cookie', 'origin', 'idempotency-key', 'if-match'}}
        # The browser session is forwarded, never replaced with a privileged key.
        # Avoid forwarding attacker-supplied host/proxy/forwarding headers.
        url = upstream + request.url.path
        if request.url.query:
            url += '?' + request.url.query
        try:
            req = client.build_request(request.method, url, headers=headers, content=await request.body())
            result = await client.send(req, stream=True)
        except httpx.HTTPError:
            return unavailable('worker-offline')
        if 300 <= result.status_code < 400:
            await result.aclose()
            return unavailable('unexpected-upstream-redirect', 502)
        if request.url.path.endswith('/export-links') and result.status_code == 200:
            try:
                await result.aread()
                links = result.json()
                for entry in links.values():
                    if isinstance(entry, dict) and isinstance(entry.get('url'), str) and entry['url'].startswith('/download/'):
                        entry['url'] = upstream + entry['url']
                return JSONResponse(links, headers={'Cache-Control': 'no-store'})
            finally:
                await result.aclose()
        response_headers = {k: v for k, v in result.headers.items() if k.lower() not in HOP_HEADERS | {'set-cookie'}}
        response = StreamingResponse(result.aiter_bytes(), status_code=result.status_code,
                                     headers=response_headers, background=BackgroundTask(result.aclose))
        for cookie in result.headers.get_list('set-cookie'):
            response.headers.append('set-cookie', cookie)
        return response

    app.mount('/static', StaticFiles(directory=str(ROOT / 'web')), name='static')
    install_documents(app)
    return app
