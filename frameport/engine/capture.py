from __future__ import annotations
import asyncio
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from playwright.async_api import async_playwright
from .network import SafeFetcher
from ..models import VIEWPORTS

EXTRACT = Path(__file__).with_name("extract.js").read_text()
FREEZE = "*,*::before,*::after{animation-play-state:paused!important;transition:none!important;caret-color:transparent!important} html{scroll-behavior:auto!important}"

async def launch_browser(pw, settings):
    return await pw.chromium.launch(
        headless=True,
        executable_path=settings.chromium_path,
        chromium_sandbox=not settings.unsandboxed_test_browser,
        args=["--disable-background-networking", "--disable-component-update", "--disable-features=WebRtcHideLocalIpsWithMdns", "--force-webrtc-ip-handling-policy=disable_non_proxied_udp", "--disable-extensions"],
    )

async def prepare_context(browser, fetcher: SafeFetcher):
    context = await browser.new_context(viewport={"width":1440,"height":900}, device_scale_factor=1, reduced_motion="reduce", service_workers="block", accept_downloads=False)
    semaphore = asyncio.Semaphore(10)
    async def route_handler(route):
        req = route.request
        if req.method not in ("GET", "HEAD") or not req.url.startswith(("https://", "http://")):
            await route.abort()
            return
        try:
            async with semaphore:
                r = await asyncio.to_thread(fetcher.get, req.url)
            await route.fulfill(status=r.status, headers=r.headers, body=r.body if req.method == "GET" else b"")
        except Exception:
            try:
                await route.abort()
            except Exception:
                pass
    await context.route("**/*", route_handler)
    await context.route_web_socket("**/*", lambda ws: ws.close())
    context.on("page", lambda p: p.on("dialog", lambda dialog: dialog.dismiss()))
    return context

async def settle(page):
    await page.wait_for_timeout(350)
    try:
        await page.evaluate("() => Promise.race([document.fonts.ready, new Promise(r=>setTimeout(r,2500))])")
        height = await page.evaluate("Math.min(document.documentElement.scrollHeight, 6000)")
        for y in range(0, int(height), 800):
            await page.evaluate("y=>window.scrollTo(0,y)", y)
            await page.wait_for_timeout(60)
        await page.evaluate("window.scrollTo(0,0)")
        await page.wait_for_timeout(200)
    except Exception:
        pass
    style = await page.add_style_tag(content=FREEZE)
    await style.evaluate("el=>el.dataset.frameportFreeze='true'")

async def screenshot(page, dest: Path):
    height = await page.evaluate("Math.max(document.documentElement.scrollHeight,document.body.scrollHeight)")
    width = page.viewport_size["width"]
    clipped = min(max(900, int(height)), 6000)
    await page.screenshot(path=str(dest), clip={"x":0,"y":0,"width":width,"height":clipped}, animations="disabled", full_page=True, timeout=15000)
    from PIL import Image
    with Image.open(dest) as image:
        if image.size != (width, clipped):
            raise ValueError("Screenshot dimensions do not match the declared evidence coverage.")
    return dict(documentHeight=height, capturedHeight=clipped, clipped=height > 6000)

def route_path(url: str) -> str:
    import re
    path = urlsplit(url).path
    parts = []
    for part in path.split("/"):
        if not part or part in (".", ".."):
            continue
        if part.lower() in ("index.html", "index.htm"):
            continue
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", part).strip("-")[:70]
        if safe:
            parts.append(safe)
    return "/" + "/".join(parts) + ("/" if parts else "")

async def capture_site(url, options, settings, root, fetcher, progress, cancelled):
    pages = []
    pending = [url]
    seen = set()
    issue_list = []
    root.joinpath("evidence").mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await launch_browser(pw, settings)
        try:
            context = await prepare_context(browser, fetcher)
            origin = None
            while pending and len(pages) < options["max_pages"]:
                if cancelled():
                    raise asyncio.CancelledError()
                current = pending.pop(0)
                if current in seen:
                    continue
                seen.add(current)
                page_index = len(pages)
                progress("Capture", 12 + page_index * 8, f"Capturing page {page_index+1}: {urlsplit(current).path or '/'}")
                page = await context.new_page()
                await page.set_viewport_size({"width":1440,"height":900})
                try:
                    response = await page.goto(current, wait_until="domcontentloaded", timeout=35000)
                    if response is None or response.status >= 400:
                        raise ValueError(f"Page returned HTTP {response.status if response else 'no response'}")
                    await settle(page)
                    captured = await page.evaluate(EXTRACT)
                    if any(p["url"].removesuffix("index.html").rstrip("/") == captured["url"].removesuffix("index.html").rstrip("/") for p in pages):
                        continue
                    seen.add(captured["url"])
                    if origin is None:
                        origin = urlsplit(captured["url"]).netloc
                    if urlsplit(captured["url"]).netloc != origin:
                        issue_list.append(dict(code="redirect",severity="warning",message="A page redirected outside the starting website and was skipped."))
                        await page.close()
                        continue
                    captured["key"] = f"p{page_index}"
                    captured["route"] = "/" if page_index == 0 else route_path(captured["url"])
                    if any(p["route"] == captured["route"] for p in pages):
                        captured["route"] = f"/page-{page_index+1}/"
                    captured["snapshots"] = []
                    for width in reversed(VIEWPORTS):
                        if cancelled():
                            raise asyncio.CancelledError()
                        if width != 1440:
                            await page.set_viewport_size({"width":width,"height":900})
                            await settle(page)
                        target = root / "evidence" / f"p{page_index}-{width}-source.png"
                        dims = await screenshot(page, target)
                        captured["snapshots"].append(dict(width=width, file=target.name, **dims))
                        if dims["clipped"]:
                            captured["warnings"].append(dict(code="coverage",severity="warning",message="Visual evidence is limited to the first 6,000 pixels of this page."))
                    captured["warnings"].append(dict(code="runtime-scope",severity="info",message="Source scripts are not shipped. Native HTML, CSS states and explicit aria-controls adapters are supported; arbitrary Framer behaviours are not verified."))
                    pages.append(captured)
                    if options["crawl"]:
                        for href in captured["links"]:
                            u = urlsplit(href)
                            if u.netloc != origin or u.query or u.scheme not in ("http","https"):
                                continue
                            if any(u.path.lower().endswith(ext) for ext in (".pdf",".zip",".png",".jpg",".jpeg",".svg",".webp",".mp4",".xml",".json")):
                                continue
                            target = urlunsplit((u.scheme,u.netloc,u.path or "/","",""))
                            if target not in seen and target not in pending and len(pending) < 40:
                                pending.append(target)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    if not pages:
                        raise ValueError(f"Could not capture the starting page: {str(e)[:240]}") from e
                    issue_list.append(dict(code="page",severity="warning",message=f"A linked page could not be captured: {str(e)[:180]}"))
                finally:
                    await page.close()
            await context.close()
        finally:
            await browser.close()
    if pending and options["crawl"]:
        issue_list.append(dict(code="page-limit", severity="info", message=f"Capture stopped at your {options['max_pages']}-page limit. Other discovered routes were not verified."))
    return dict(version=1, pages=pages, issues=issue_list, discovered=len(seen)+len(pending))
