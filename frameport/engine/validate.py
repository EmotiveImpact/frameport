from __future__ import annotations
import asyncio
import functools
import http.server
import threading
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from PIL import Image, ImageChops
from playwright.async_api import async_playwright
from .capture import launch_browser, settle, screenshot
from .compiler import page_file
from ..models import VIEWPORTS

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

@contextmanager
def local_site(directory: Path):
    handler = functools.partial(QuietHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1",0),handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

def compare_images(source: Path, result: Path, diff: Path):
    with Image.open(source) as opened:
        a = opened.convert("RGB")
    with Image.open(result) as opened:
        b = opened.convert("RGB")
    size_equal = a.size == b.size
    w, h = max(a.width,b.width),max(a.height,b.height)
    aa, bb = Image.new("RGB",(w,h),"white"),Image.new("RGB",(w,h),"white")
    aa.paste(a,(0,0)); bb.paste(b,(0,0))
    delta = ImageChops.difference(aa,bb)
    r,g,bl = delta.split()
    strongest = ImageChops.lighter(ImageChops.lighter(r,g),bl)
    mask = strongest.point(lambda p:255 if p>22 else 0)
    changed = mask.histogram()[255]
    total = w*h
    overlay = Image.blend(aa,Image.new("RGB",(w,h),(245,76,136)),0.75)
    aa.paste(overlay,(0,0),mask)
    aa.save(diff,optimize=True)
    ratio = changed/total
    return dict(changedPixels=changed,totalPixels=total,difference=round(ratio,6),matchedPixels=round((1-ratio)*100,3),dimensionsMatch=size_equal,passed=size_equal and ratio<=0.02,threshold=0.02,channelTolerance=22)

async def validate(ir, root, settings, progress, cancelled):
    comparisons = []
    checks = []
    resource_failures = set()
    browser_errors = []
    with local_site(root/"html") as origin:
        async with async_playwright() as pw:
            browser = await launch_browser(pw,settings)
            try:
                context = await browser.new_context(viewport={"width":1440,"height":900},device_scale_factor=1,reduced_motion="reduce",service_workers="block")
                async def restrict(route):
                    if route.request.url.startswith(origin+"/") and route.request.method in ("GET","HEAD"):
                        await route.continue_()
                    else:
                        resource_failures.add(route.request.url[:250])
                        await route.abort()
                await context.route("**/*",restrict)
                await context.route_web_socket("**/*",lambda ws:ws.close())
                for i,p in enumerate(ir["pages"]):
                    progress("Verify",72+i*5,f"Comparing {p['route']} at five responsive widths")
                    for width in reversed(VIEWPORTS):
                        if cancelled(): raise asyncio.CancelledError()
                        page = await context.new_page()
                        page.on("pageerror",lambda error:browser_errors.append(str(error)[:300]))
                        await page.set_viewport_size({"width":width,"height":900})
                        response = await page.goto(origin+"/"+page_file(p),wait_until="load",timeout=20000)
                        await settle(page)
                        output = root/"evidence"/f"{p['key']}-{width}-export.png"
                        dims = await screenshot(page,output)
                        reference = root/"evidence"/f"{p['key']}-{width}-source.png"
                        difference = root/"evidence"/f"{p['key']}-{width}-diff.png"
                        result = await asyncio.to_thread(compare_images,reference,output,difference)
                        comparisons.append(dict(page=p["key"],route=p["route"],width=width,source=reference.name,export=output.name,diff=difference.name,**dims,**result))
                        broken = await page.locator("img").evaluate_all("xs=>xs.filter(x=>!x.complete || x.naturalWidth===0).length")
                        overflow = await page.evaluate("document.documentElement.scrollWidth>window.innerWidth+2")
                        checks.append(dict(name="render",page=p["key"],width=width,passed=response.status==200 and not broken,brokenImages=broken,horizontalOverflow=overflow))
                        if width in (1440,390):
                            for details in await page.locator("details").all():
                                summary = details.locator("summary").first
                                if await summary.count() and await summary.is_visible():
                                    before = await details.evaluate("e=>e.open")
                                    await summary.click()
                                    after = await details.evaluate("e=>e.open")
                                    checks.append(dict(name="native-disclosure",page=p["key"],passed=before!=after))
                            for button in await page.locator("button[aria-controls]").all():
                                if not await button.is_visible(): continue
                                ident = await button.get_attribute("aria-controls")
                                target_exists = await page.evaluate("id=>!!document.getElementById(id)",ident)
                                before = await button.get_attribute("aria-expanded")
                                await button.click()
                                after = await button.get_attribute("aria-expanded")
                                checks.append(dict(name="aria-disclosure",page=p["key"],passed=target_exists and before!=after))
                        await page.close()
                await context.close()
            finally:
                await browser.close()
    issues = list(ir["issues"])
    for p in ir["pages"]:
        issues += [dict(x,page=p["route"]) for x in p["warnings"]]
    if resource_failures:
        issues.append(dict(code="external-resources",severity="warning",message=f"{len(resource_failures)} resource requests were blocked during the independent preview. Review missing dependencies."))
    if browser_errors:
        issues.append(dict(code="browser-errors",severity="warning",message=f"{len(browser_errors)} JavaScript errors occurred in the generated HTML."))
    # Merge repeats, preserving counts rather than overwhelming the UI.
    grouped = {}
    for issue in issues:
        key = (issue.get("code"),issue.get("message"),issue.get("page",""))
        if key in grouped: grouped[key]["count"] += 1
        else: grouped[key] = dict(issue,count=1)
    issues = list(grouped.values())
    visual_pass = bool(comparisons) and all(c["passed"] for c in comparisons)
    behaviour_pass = all(c["passed"] for c in checks) and not browser_errors
    return dict(
        version=1,verdict="visual-pass" if visual_pass and behaviour_pass and not resource_failures else "needs-review",
        visualPassed=visual_pass,checksPassed=behaviour_pass,comparisons=comparisons,checks=checks,issues=issues,
        externalRequests=sorted(resource_failures),browserErrors=browser_errors,
        coverage=dict(pages=len(ir["pages"]),widths=VIEWPORTS,maxHeight=6000,colourScheme="light",motion="reduced",target="HTML reconstruction",states="Initial page; native details and visible aria-controls disclosures only"),
        reactBuild=dict(status="not-run",message="React source is generated. Its npm install, strict type check and production build must be run separately; HTML screenshot results do not verify React."),
        caveat="Visual pass refers only to the captured HTML states, not complete functional equivalence, all breakpoints, backend migration or the original Framer source.",
    )
