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
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles
from .config import ROOT, Settings
from .models import ConvertRequest, EditRequest
from .store import Store
from .engine.network import normalise_url, NetworkError
from .engine.pipeline import run_guarded

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
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=settings.max_pending)
    stop = asyncio.Event()
    started = time.time()

    async def worker():
        while not stop.is_set():
            ident = await queue.get()
            try:
                record = store.get(ident)
                if record and not record.get("cancelled") and record["status"] == "queued":
                    await run_guarded(record,store,settings)
            finally:
                queue.task_done()

    @asynccontextmanager
    async def lifespan(app):
        cutoff = time.time()-settings.retention_days*86400
        for record in store.list(10000):
            if record["created"] < cutoff:
                shutil.rmtree(settings.data/"jobs"/record["id"],ignore_errors=True)
                store.delete(record["id"])
            elif record["status"] in ("running","queued"):
                store.update(record["id"],status="failed",stage="Interrupted",error="The worker restarted before this export completed. Use Retry.")
        workers = [asyncio.create_task(worker()) for _ in range(settings.workers)]
        yield
        stop.set()
        for task in workers: task.cancel()
        await asyncio.gather(*workers,return_exceptions=True)

    app = FastAPI(title="Frameport",version="0.1.0",lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=list(settings.allowed_hosts))
    app.state.store, app.state.settings, app.state.queue = store,settings,queue

    @app.middleware("http")
    async def headers(request: Request, call_next):
        if request.method not in ("GET","HEAD","OPTIONS"):
            origin = request.headers.get("origin")
            # Same-origin browser writes only. CLI requests use the API key or loopback.
            if origin and origin != f"{request.url.scheme}://{request.headers.get('host','')}":
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
        if request.url.path.startswith(("/api/","/preview/","/evidence/")):
            response.headers["Cache-Control"] = "no-store"
        return response

    async def authenticated(request: Request, authorization: str | None = Header(default=None)):
        if settings.api_key:
            supplied = authorization.removeprefix("Bearer ") if authorization else ""
            if not hmac.compare_digest(supplied,settings.api_key):
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
        if number < time.time() or number > time.time()+1900 or not hmac.compare_digest(signature,expected):
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
        return dict(name="Frameport",version="0.1.0",worker="available",authRequired=bool(settings.api_key),sandboxed=not settings.unsandboxed_test_browser,uptime=int(time.time()-started),publicService=False)

    @app.get("/api/jobs",dependencies=[Depends(authenticated)])
    async def jobs():
        return [present(r) for r in store.list()]

    def schedule(request):
        if not request.permission:
            raise HTTPException(422,"Confirm that you own the site or have permission to export it.")
        if not request.demo:
            try: request.url = normalise_url(request.url)
            except NetworkError as e: raise HTTPException(422,str(e))
        else: request.url = "frameport://forma-demo"
        if queue.full(): raise HTTPException(429,"The conversion queue is full. Try again after a job completes.")
        used = sum(p.stat().st_size for p in settings.data.rglob("*") if p.is_file())
        if used > settings.max_storage_bytes: raise HTTPException(507,"Workspace storage is full. Delete old conversions first.")
        if request.bridge:
            if request.demo:
                raise HTTPException(422,"Project manifests require a published website, not the sample site.")
            if normalise_url(request.bridge.publishedUrl) != request.url:
                raise HTTPException(422,"Manifest URL must match the conversion URL.")
        record = store.create(request.model_dump(by_alias=True))
        queue.put_nowait(record["id"])
        return present(record)

    @app.post("/api/jobs",status_code=202,dependencies=[Depends(authenticated)])
    async def create_job(request: ConvertRequest):
        return schedule(request)

    @app.get("/api/jobs/{ident}",dependencies=[Depends(authenticated)])
    async def get_job(ident: str):
        return present(required(ident))

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
        if queue.full(): raise HTTPException(429,"The conversion queue is full.")
        ir = json.loads((root/"model.json").read_text())
        if any(p.id not in ir["texts"] for p in request.patches): raise HTTPException(422,"An edit references an unknown content field.")
        changed = store.update(ident,status="queued",stage="Queued",progress=0,cancelled=False,revision=job["revision"]+1,pendingPatches=[p.model_dump() for p in request.patches],report=None)
        (root/"COMPLETE").unlink(missing_ok=True)
        queue.put_nowait(ident)
        return present(changed)

    @app.get("/api/jobs/{ident}/download/{target}",dependencies=[Depends(authenticated)])
    async def download(ident: str,target: str):
        _,root = complete(ident)
        if target not in ("react","html"): raise HTTPException(404,"Export not found")
        return FileResponse(root/f"{target}.zip",media_type="application/zip",filename=f"frameport-{target}-{ident[:8]}.zip")

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
    @app.get("/")
    async def index(): return FileResponse(ROOT/"web"/"index.html")
    return app
