"""Real-browser checks of Frameport's authored UI and original WebGL artwork.

No public source websites are visited. Software GL is an explicit CI rendering
option, not a change to the production browser's sandbox/network configuration.
"""
from __future__ import annotations
import argparse
import asyncio
import json
from pathlib import Path
from PIL import Image, ImageChops
from playwright.async_api import async_playwright, expect
from frameport.config import Settings
from scripts.check_acceptance import http_worker


async def run(output: Path, software_gl: bool, portable: Path | None = None):
    output.mkdir(parents=True, exist_ok=True)
    result = {"scope": "Authored monochrome studio and original shader", "mode": "portable-local-document" if portable else "real-http", "softwareGL": software_gl, "checks": [], "errors": [], "passed": False}
    def check(name, ok):
        result["checks"].append({"name": name, "passed": bool(ok)})
        if not ok:
            raise AssertionError(name)
    settings = Settings(data=output / "private-workspace")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, executable_path=settings.chromium_path, chromium_sandbox=not settings.unsandboxed_test_browser, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] if software_gl else [])
        try:
            with http_worker(settings) as origin:
                async def open_app(page):
                    page.on("pageerror", lambda e: result["errors"].append(str(e)))
                    if portable:
                        await page.set_content(portable.read_text(), wait_until="domcontentloaded")
                    else:
                        await page.goto(origin, wait_until="networkidle")
                    await page.locator("#hero-title").wait_for()
                context = await browser.new_context(viewport={"width":1440,"height":1000},device_scale_factor=1)
                page = await context.new_page()
                await open_app(page)
                check("Black application background", await page.evaluate("getComputedStyle(document.documentElement).backgroundColor === 'rgb(0, 0, 0)'"))
                check("Top navigation replaces sidebar", await page.locator(".main-nav").is_visible() and await page.locator(".sidebar").count() == 0)
                check("Real conversion form remains available", await page.locator("#conversion-form").count() == 1)
                renderer = await page.locator(".hero-visual").get_attribute("data-renderer")
                result["renderer"] = renderer
                if portable and renderer != "webgl":
                    check("Local WebGL unavailable, labelled CSS fallback", await page.locator("#motion-toggle").inner_text() == "Static artwork")
                    result["webglVerified"] = False
                else:
                    await expect(page.locator(".hero-visual")).to_have_attribute("data-renderer", "webgl")
                    check("Shader compiles and links in WebGL", True)
                    result["webglVerified"] = True
                    await page.wait_for_timeout(250)
                    before = int(await page.locator("#hero-shader").get_attribute("data-frames"))
                    await page.locator("#hero-shader").screenshot(path=str(output / "shader-a.png"))
                    await page.wait_for_timeout(1400)
                    after = int(await page.locator("#hero-shader").get_attribute("data-frames"))
                    await page.locator("#hero-shader").screenshot(path=str(output / "shader-b.png"))
                    check("Animation draws new frames", after > before)
                    with Image.open(output / "shader-a.png") as a, Image.open(output / "shader-b.png") as b:
                        check("Rendered shader pixels actually change", ImageChops.difference(a.convert('RGB'), b.convert('RGB')).getbbox() is not None)
                        r,g,bl = b.convert('RGB').split()
                        check("Artwork is monochrome, not tinted", ImageChops.difference(r,g).getextrema()[1] <= 1 and ImageChops.difference(g,bl).getextrema()[1] <= 1)
                        histogram = r.histogram()
                        check("Artwork contains a visible luminous edge", sum(histogram[80:]) > 50)
                        check("Negative space stays predominantly black", sum(histogram[:12]) / (b.width*b.height) > 0.65)
                    await page.locator("#motion-toggle").click()
                    await expect(page.locator(".hero-visual")).to_have_attribute("data-motion", "paused")
                    paused_frames = await page.locator("#hero-shader").get_attribute("data-frames")
                    await page.wait_for_timeout(350)
                    check("Pause stops the animation loop", paused_frames == await page.locator("#hero-shader").get_attribute("data-frames"))
                    await page.screenshot(path=str(output / "desktop-home.png"), full_page=True)
                    await page.locator("#motion-toggle").click()
                    await page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                    await expect(page.locator(".hero-visual")).to_have_attribute("data-motion", "hidden")
                    frames = await page.locator("#hero-shader").get_attribute("data-frames")
                    await page.wait_for_timeout(300)
                    check("Offscreen artwork stops drawing", frames == await page.locator("#hero-shader").get_attribute("data-frames"))
                    await page.evaluate("window.scrollTo(0,0)")
                    await expect(page.locator(".hero-visual")).to_have_attribute("data-motion", "running")
                    check("Artwork resumes when visible", True)
                    await page.emulate_media(reduced_motion="reduce")
                    await expect(page.locator(".hero-visual")).to_have_attribute("data-motion", "reduced")
                    frames = await page.locator("#hero-shader").get_attribute("data-frames")
                    await page.wait_for_timeout(300)
                    check("Reduced motion renders a still frame", frames == await page.locator("#hero-shader").get_attribute("data-frames") and await page.locator("#motion-toggle").is_disabled())
                    await page.emulate_media(reduced_motion="no-preference")
                    can_lose = await page.locator("#hero-shader").evaluate("c => { c.testExtension=c.getContext('webgl').getExtension('WEBGL_lose_context'); return !!c.testExtension; }")
                    check("Context-loss test extension available", can_lose)
                    await page.locator("#hero-shader").evaluate("c => c.testExtension.loseContext()")
                    await expect(page.locator(".hero-visual")).to_have_attribute("data-renderer", "fallback")
                    check("Context loss shows static fallback", True)
                    await page.wait_for_timeout(350)
                    await page.locator("#hero-shader").evaluate("c => c.testExtension.restoreContext()")
                    await expect(page.locator(".hero-visual")).to_have_attribute("data-renderer", "webgl", timeout=10000)
                    check("Context restoration rebuilds GPU resources", True)
                    old = await page.locator("#hero-shader").element_handle()
                    await page.locator(".main-nav [data-view='docs']").click()
                    previous = await old.get_attribute("data-frames")
                    await page.wait_for_timeout(350)
                    check("Leaving the hero disposes its animation", not await old.evaluate("c => c.isConnected") and previous == await old.get_attribute("data-frames"))
                    await page.locator(".main-nav [data-view='overview']").click()
                    await expect(page.locator(".hero-visual")).to_have_attribute("data-renderer", "webgl")
                    check("Returning mounts a fresh renderer", True)
                    check("GPU pixel budget is bounded", await page.locator("#hero-shader").evaluate("c => c.width*c.height <= 1405000"))
                if renderer != "webgl":
                    await page.screenshot(path=str(output / "desktop-home.png"), full_page=True)
                await page.locator("#start-converting").click()
                check("Start converting focuses the live URL input", await page.locator("#url").evaluate("e => e === document.activeElement"))
                await page.locator("#options-toggle").click()
                check("Advanced settings remain operable", await page.locator("#export-options").is_visible())
                await page.locator("#bridge-tab").click()
                check("Manifest import remains available", await page.locator("#manifest-input").count() == 1)
                for width in [1440,1024,768,390,320]:
                    await page.set_viewport_size({"width":width,"height":900})
                    await page.locator(".main-nav [data-view='overview']").click()
                    await page.wait_for_timeout(100)
                    check(f"Overview fits {width}px", await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"))
                    check(f"Workspace connection accessible at {width}px", await page.locator("#workspace-button").is_visible())
                    for view in ['history','docs']:
                        await page.locator(f".main-nav [data-view='{view}']").click()
                        check(f"{view} fits {width}px", await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"))
                    if width == 390:
                        await page.locator(".main-nav [data-view='overview']").click()
                        await page.emulate_media(reduced_motion="reduce")
                        await page.screenshot(path=str(output / "mobile-home.png"), full_page=True)
                await context.close()
                # Deliberately emulate a device without WebGL. Keep all form logic real.
                fallback = await browser.new_context(viewport={"width":1440,"height":900})
                await fallback.add_init_script("const get=HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext=function(type,...args){return String(type).includes('webgl')?null:get.call(this,type,...args)};")
                p = await fallback.new_page()
                await open_app(p)
                await expect(p.locator('.hero-visual')).to_have_attribute('data-renderer','fallback')
                check("WebGL absence does not break the app", await p.locator('#url').is_enabled())
                await p.locator('#start-converting').click()
                await p.locator('#url').fill('https://example.com')
                check("Fallback keeps inputs usable", await p.locator('#url').input_value() == 'https://example.com')
                await fallback.close()
                check("No uncaught browser errors", not result['errors'])
                result['passed'] = True
        except Exception as error:
            result['error'] = f'{type(error).__name__}: {error}'
        finally:
            await browser.close()
            (output / 'design-checks.json').write_text(json.dumps(result,indent=2))
            print(json.dumps(result,indent=2),flush=True)
    return result['passed']

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('artifacts/design'))
    parser.add_argument('--software-gl',action='store_true')
    parser.add_argument('--portable',type=Path,help='Explicit authored-file UI test; cannot claim real HTTP or unavailable WebGL verification.')
    args=parser.parse_args()
    if not asyncio.run(run(args.output.resolve(),args.software_gl,args.portable)):
        raise SystemExit(1)
