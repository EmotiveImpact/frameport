from __future__ import annotations
import asyncio
import contextlib
import hashlib
import hmac
import json
import mimetypes
import secrets
import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, Query
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles
from .config import ROOT, Settings
from .models import ConvertRequest, EditRequest, SessionRequest, RenameRequest
from .store import Store
from .engine.network import normalise_url, NetworkError
from .worker import Supervisor
from .platform_store import QueueFull, Conflict
from .web_routes import install_documents

PREVIEW_CSP = "sandbox allow-scripts; default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; media-src 'self'; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
APP_CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"

def safe_path(root: Path, relative: str) -> Path:
    if not relative or "\x00" in relative or "\\" in relative:
        raise HTTPException(404,"File not found")
    dest = (root/relative).resolve()
    if not dest.is_relative_to(root.resolve()) or not dest.is_file():
        raise HTTPException(404,"File not found")
    return dest

def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    settings.data.mkdir(parents=True,exist_ok=True)
    store = Store(settings.data)
    signing_file = settings.data/"preview.key"
    if not signing_file.exists():
        signing_file.write_bytes(secrets.token_bytes(32))
        signing_file.chmod(0o600)
    signing_key = signing_file.read_bytes()
    supervisor = Supervisor(store, settings)
    started = time.time()

    @asynccontextmanager
    async def lifespan(app):
        app.state.started = True
        cutoff = time.time()-settings.retention_days*86400
        # Queued jobs survive restarts. Only inactive projects are eligible for cleanup.
        for record in store.list(10000):
            if record["updated"] < cutoff and record['status'] not in ('running', 'queued'):
                shutil.rmtree(settings.data/"jobs"/record["id"], ignore_errors=True)
                store.delete(record["id"])
        await supervisor.start()
        try:
            yield
        finally:
            await supervisor.close()

    app = FastAPI(title="Frameport",version="0.2.0",lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=list(settings.allowed_hosts))
    app.state.store, app.state.settings, app.state.supervisor = store,settings,supervisor
    app.state.started = False

    @app.middleware("http")
    async def headers(request: Request, call_next):
        if request.method not in ("GET","HEAD","OPTIONS"):
            origin = request.headers.get("origin")
            # Same-origin browser writes only. CLI requests use the API key or loopback.
            if origin and origin not in {settings.public_origin, f"{request.url.scheme}://{request.headers.get('host','')}"}:
                return JSONResponse({"detail":"Cross-origin writes are not allowed."},status_code=403)
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return JSONResponse({"detail":"Use application/json for API writes."},status_code=415)
            length = request.headers.get("content-length")
            if length and (not length.isdigit() or int(length)>1_200_000):
                return JSONResponse({"detail":"Request body is too large."},status_code=413)
            size = 0
            chunks = []
            async for chunk in request.stream():
                size += len(chunk)
                if size > 1_200_000:
                    return JSONResponse({"detail":"Request body is too large."},status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        response.headers.setdefault("Content-Security-Policy",APP_CSP)
        if request.url.path.startswith(("/api/","/preview/","/evidence/","/download/")):
            response.headers["Cache-Control"] = "no-store"
        return response

    async def authenticated(request: Request, authorization: str | None = Header(default=None)):
        if settings.api_key:
            supplied = authorization.removeprefix("Bearer ") if authorization else ""
            if not hmac.compare_digest(supplied.encode(), settings.api_key.encode()) and not store.valid_session(request.cookies.get("frameport_session", ""), settings.api_key):
                raise HTTPException(401,"Enter this worker's access key to continue.")
        elif not request.client or request.client.host not in ("127.0.0.1","::1","testclient"):
            raise HTTPException(403,"This worker is in local-only mode. Configure an access key before remote use.")

    def required(ident):
        if not __import__('re').fullmatch(r"[0-9a-f]{32}",ident):
            raise HTTPException(404,"Conversion not found")
        job = store.get(ident)
        if not job: raise HTTPException(404,"Conversion not found")
        return job

    def complete(ident):
        job = required(ident)
        root = settings.data/"jobs"/ident
        if job["status"] != "completed" or not (root/"COMPLETE").is_file():
            raise HTTPException(409,"This conversion does not have a completed export.")
        return job,root

    def ticket(ident,revision):
        expiry = int(time.time())+1800
        message = f"{ident}:{revision}:{expiry}"
        signature = hmac.new(signing_key,message.encode(),hashlib.sha256).hexdigest()
        return f"{expiry}-{signature}"

    def verify_ticket(ident,token):
        job,root = complete(ident)
        try:
            expiry,signature = token.split("-",1)
            number = int(expiry)
        except ValueError:
            raise HTTPException(403,"Invalid preview access")
        expected = hmac.new(signing_key,f"{ident}:{job['revision']}:{number}".encode(),hashlib.sha256).hexdigest()
        if number < time.time() or number > time.time()+1900 or not hmac.compare_digest(signature.encode(), expected.encode()):
            raise HTTPException(403,"Preview link expired. Reload the conversion.")
        return root

    def present(job):
        r = dict(job)
        r.pop("pendingPatches",None)
        r["request"] = {k:v for k,v in job["request"].items() if k != "bridge"}
        r["hasBridge"] = bool(job["request"].get("bridge"))
        if job["status"] == "completed": r["ticket"] = ticket(job["id"],job["revision"])
        return r

    @app.get("/api/health")
    async def health():
        counts = store.counts()
        return dict(name="Frameport", version="0.2.0", deployment="persistent-worker", worker="available" if supervisor.ready else "offline",
                    authRequired=bool(settings.api_key), canConvert=supervisor.ready, message=supervisor.message,
                    sandboxed=not settings.unsandboxed_test_browser, storage="persistent-volume" if settings.managed_storage else "local-disk",
                    uptime=int(time.time()-started), publicService=False, queueDepth=counts.get('queued', 0), activeJobs=counts.get('running', 0))

    @app.get('/api/ready')
    async def readiness():
        result = await health()
        return JSONResponse(result, status_code=200 if result['canConvert'] else 503)

    @app.get('/api/session')
    async def session(request: Request, authorization: str | None = Header(default=None)):
        try:
            await authenticated(request, authorization)
            connected = True
        except HTTPException:
            connected = False
        return dict(authenticated=connected, authRequired=bool(settings.api_key), workspace='Emotive workspace', role='owner' if connected else None)

    @app.post('/api/session')
    async def login(request: Request, credentials: SessionRequest, response: Response):
        bucket = hashlib.sha256((request.client.host if request.client else 'unknown').encode()).hexdigest()
        if not store.allow_login(bucket):
            raise HTTPException(429, 'Too many sign-in attempts. Wait five minutes before trying again.')
        if not settings.api_key or not hmac.compare_digest(credentials.key.encode(), settings.api_key.encode()):
            raise HTTPException(401, 'The workspace access key is incorrect.')
        token = store.create_session(settings.api_key, settings.session_days)
        secure_cookie = settings.public_origin.startswith('https://') or request.url.scheme == 'https'
        response.set_cookie('frameport_session', token, max_age=settings.session_days*86400, httponly=True,
                            secure=secure_cookie, samesite='strict', path='/')
        return dict(authenticated=True, workspace='Emotive workspace', role='owner')

    @app.delete('/api/session')
    async def logout(request: Request, response: Response):
        store.logout(request.cookies.get('frameport_session', ''))
        response.delete_cookie('frameport_session', path='/')
        return dict(authenticated=False)

    @app.get("/api/projects", dependencies=[Depends(authenticated)])
    @app.get("/api/jobs",dependencies=[Depends(authenticated)])
    async def jobs(limit: int = Query(default=100, ge=1, le=500)):
        return [present(r) for r in store.list(limit)]

    def schedule(request, idempotency_key=None):
        if app.state.started and not supervisor.ready:
            raise HTTPException(503, "The browser worker is not ready. Check workspace settings.")
        if not request.permission:
            raise HTTPException(422,"Confirm that you own the site or have permission to export it.")
        if not request.demo:
            try: request.url = normalise_url(request.url)
            except NetworkError as e: raise HTTPException(422,str(e))
        else: request.url = "frameport://forma-demo"

        used = sum(p.stat().st_size for p in settings.data.rglob("*") if p.is_file())
        if used > settings.max_storage_bytes: raise HTTPException(507,"Workspace storage is full. Delete old conversions first.")
        if request.bridge:
            if request.demo:
                raise HTTPException(422,"Project manifests require a published website, not the sample site.")
            if normalise_url(request.bridge.publishedUrl) != request.url:
                raise HTTPException(422,"Manifest URL must match the conversion URL.")
        try:
            record = store.enqueue(request.model_dump(by_alias=True), settings.max_pending, idempotency_key)
        except QueueFull as error:
            raise HTTPException(429, str(error))
        except Conflict as error:
            raise HTTPException(409, str(error))
        return present(record)

    @app.post("/api/jobs",status_code=202,dependencies=[Depends(authenticated)])
    async def create_job(request: ConvertRequest, idempotency_key: str | None = Header(default=None, max_length=128)):
        return schedule(request, idempotency_key)

    @app.get("/api/jobs/{ident}",dependencies=[Depends(authenticated)])
    async def get_job(ident: str):
        return present(required(ident))

    @app.patch('/api/jobs/{ident}', dependencies=[Depends(authenticated)])
    async def rename_job(ident: str, request: RenameRequest):
        required(ident)
        name = request.name.strip()
        if not name:
            raise HTTPException(422, 'Enter a project name.')
        return present(store.rename(ident, name))

    @app.get('/api/jobs/{ident}/revisions', dependencies=[Depends(authenticated)])
    async def revisions(ident: str):
        required(ident)
        store.record_revision(ident)
        return store.revisions(ident)

    @app.post("/api/jobs/{ident}/cancel",dependencies=[Depends(authenticated)])
    async def cancel(ident: str):
        job = required(ident)
        if job["status"] not in ("queued","running"):
            raise HTTPException(409,"Only active conversions can be cancelled.")
        values = dict(cancelled=True)
        if job["status"] == "queued": values.update(status="cancelled",stage="Cancelled")
        return present(store.update(ident,**values))

    @app.post("/api/jobs/{ident}/retry",status_code=202,dependencies=[Depends(authenticated)])
    async def retry(ident: str):
        job = required(ident)
        return schedule(ConvertRequest(**job["request"]))

    @app.delete("/api/jobs/{ident}",dependencies=[Depends(authenticated)])
    async def delete(ident: str):
        job = required(ident)
        if job["status"] in ("queued","running"): raise HTTPException(409,"Cancel the conversion before deleting it.")
        shutil.rmtree(settings.data/"jobs"/ident,ignore_errors=True)
        store.delete(ident)
        return {"deleted":True}

    @app.get("/api/jobs/{ident}/files",dependencies=[Depends(authenticated)])
    async def files(ident: str, target: str = "react"):
        _,root = complete(ident)
        if target not in ("react","html"): raise HTTPException(422,"Unknown export target")
        allowed = {".ts",".tsx",".js",".json",".css",".html",".md",".svg",".gitignore"}
        return [dict(path=str(p.relative_to(root/target)),bytes=p.stat().st_size) for p in sorted((root/target).rglob("*")) if p.is_file() and (p.suffix in allowed or p.name==".gitignore")]

    @app.get("/api/jobs/{ident}/file",dependencies=[Depends(authenticated)])
    async def file(ident: str, path: str, target: str = "react"):
        _,root = complete(ident)
        if target not in ("react","html"): raise HTTPException(422,"Unknown export target")
        p = safe_path(root/target,path)
        if p.stat().st_size > 1_000_000 or (p.suffix not in (".ts",".tsx",".js",".json",".css",".html",".md",".svg") and p.name != ".gitignore"):
            raise HTTPException(422,"This file is not available in the source viewer.")
        return dict(path=path,content=p.read_text())

    @app.get("/api/jobs/{ident}/content",dependencies=[Depends(authenticated)])
    async def content(ident: str):
        _,root = complete(ident)
        ir = json.loads((root/"model.json").read_text())
        return [dict(id=k,text=v) for k,v in ir["texts"].items() if v.strip()]

    @app.post("/api/jobs/{ident}/edits",status_code=202,dependencies=[Depends(authenticated)])
    async def edits(ident: str, request: EditRequest):
        job,root = complete(ident)
        if app.state.started and not supervisor.ready:
            raise HTTPException(503, "The browser worker is not ready.")
        ir = json.loads((root/"model.json").read_text())
        if any(p.id not in ir["texts"] for p in request.patches): raise HTTPException(422,"An edit references an unknown content field.")
        try:
            changed = store.queue_edits(ident, [p.model_dump() for p in request.patches], request.expected_revision, settings.max_pending)
        except Conflict as error:
            raise HTTPException(409, str(error))
        except QueueFull as error:
            raise HTTPException(429, str(error))
        (root/"COMPLETE").unlink(missing_ok=True)
        return present(changed)

    @app.get("/api/jobs/{ident}/download/{target}",dependencies=[Depends(authenticated)])
    async def download(ident: str,target: str):
        _,root = complete(ident)
        if target not in ("react","html"): raise HTTPException(404,"Export not found")
        return FileResponse(root/f"{target}.zip",media_type="application/zip",filename=f"frameport-{target}-{ident[:8]}.zip")

    @app.get('/api/jobs/{ident}/export-links', dependencies=[Depends(authenticated)])
    async def export_links(ident: str):
        job, root = complete(ident)
        links = {}
        for target in ('react', 'html'):
            expiry = int(time.time())+300
            signature = hmac.new(signing_key, f'download:{ident}:{job["revision"]}:{target}:{expiry}'.encode(), hashlib.sha256).hexdigest()
            links[target] = dict(url=f'/download/{ident}/{expiry}-{signature}/{target}', expiresAt=expiry,
                                 bytes=(root/f'{target}.zip').stat().st_size, revision=job['revision'])
        return links

    @app.get('/download/{ident}/{token}/{target}')
    async def signed_download(ident: str, token: str, target: str):
        job, root = complete(ident)
        if target not in ('html', 'react'):
            raise HTTPException(404, 'Export not found')
        try:
            expiry, signature = token.split('-', 1); expiry = int(expiry)
        except ValueError:
            raise HTTPException(403, 'Invalid download link')
        expected = hmac.new(signing_key, f'download:{ident}:{job["revision"]}:{target}:{expiry}'.encode(), hashlib.sha256).hexdigest()
        if expiry < time.time() or expiry > time.time()+310 or not hmac.compare_digest(signature.encode(), expected.encode()):
            raise HTTPException(403, 'Download link expired. Request a new one from the project.')
        return FileResponse(root/f'{target}.zip', media_type='application/zip', filename=f'frameport-{target}-{ident[:8]}-r{job["revision"]}.zip', headers={'Cache-Control':'no-store'})

    @app.get("/api/jobs/{ident}/report",dependencies=[Depends(authenticated)])
    async def report(ident: str):
        _,root = complete(ident)
        return FileResponse(root/"report.json",media_type="application/json",filename="frameport-verification.json")

    @app.get("/preview/{ident}/{token}/{path:path}")
    async def preview(ident: str,token: str,path: str):
        root = verify_ticket(ident,token)
        if not path or path.endswith("/"): path += "index.html"
        p = safe_path(root/"html",path)
        if p.suffix.lower() not in (".html",".css",".js",".png",".jpg",".jpeg",".svg",".webp",".avif",".gif",".ico",".woff",".woff2",".ttf",".otf",".mp4",".webm",".mp3",".ogg"):
            raise HTTPException(404,"Preview file not found")
        return FileResponse(p,headers={"Content-Security-Policy":PREVIEW_CSP})

    @app.get("/evidence/{ident}/{token}/{path}")
    async def evidence(ident: str,token: str,path: str):
        root = verify_ticket(ident,token)
        if not __import__('re').fullmatch(r"p\d+-\d+-(source|export|diff)\.png",path): raise HTTPException(404,"Evidence not found")
        return FileResponse(safe_path(root/"evidence",path),media_type="image/png")

    app.mount("/static",StaticFiles(directory=str(ROOT/"web")),name="static")
    install_documents(app)
    return app
