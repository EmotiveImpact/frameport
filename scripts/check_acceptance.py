"""Real HTTP/browser acceptance for the authored fixture, never an offline substitute.

Run after check_fixture and the generated React npm production build. Uses an
isolated copy for editing, leaving the reference build and report unchanged.
"""
from __future__ import annotations
import argparse
import asyncio
from contextlib import contextmanager
import json
from pathlib import Path
import re
import secrets
import shutil
import socket
import threading
import time
import zipfile

import uvicorn
from playwright.async_api import async_playwright, expect
from frameport.app import create_app
from frameport.config import Settings
from frameport.engine.capture import launch_browser, settle, screenshot
from frameport.engine.compiler import page_file
from frameport.engine.validate import compare_images, local_site
from frameport.store import Store


def load_fixture(result: Path, data: Path):
    job = json.loads(result.read_text())
    ident = job.get("id", "")
    if not re.fullmatch(r"[0-9a-f]{32}", ident):
        raise ValueError("Invalid fixture job identifier")
    if job.get("status") != "completed" or not job.get("request", {}).get("demo"):
        raise ValueError("Acceptance only runs on the completed, authored demo fixture")
    if job.get("report", {}).get("execution", {}).get("mode") == "offline-document-harness":
        raise ValueError("Real-navigation acceptance cannot use offline reference evidence")
    root = data.resolve() / "jobs" / ident
    for relative in ("COMPLETE", "model.json", "react/dist/index.html"):
        if not (root / relative).is_file():
            raise ValueError(f"Missing fixture/build prerequisite: {relative}")
    return job, root


@contextmanager
def http_worker(settings: Settings):
    """Bind first, then start Uvicorn with its real ASGI lifespan and worker."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(settings), log_level="warning"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 15
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Acceptance worker failed to start")
            time.sleep(0.05)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        sock.close()


async def run(result_file: Path, data: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    result = {"scope": "Authored Forma fixture; real HTTP, installed React production build and authenticated studio", "checks": [], "reactComparisons": [], "browserErrors": [], "externalRequests": [], "passed": False}
    def check(name, condition):
        result["checks"].append({"name": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)
    try:
        job, source = load_fixture(result_file, data)
        result["referenceJob"] = job["id"]
        result["referenceRevision"] = job["revision"]
        ir = json.loads((source / "model.json").read_text())
        settings = Settings(data=output / "private-workspace", api_key=secrets.token_urlsafe(32))
        store = Store(settings.data)
        copy = store.create(job["request"])
        destination = settings.data / "jobs" / copy["id"]
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns("node_modules", "dist", "package-lock.json"))
        store.update(copy["id"], status="completed", stage="Complete", progress=100, report=job["report"])
        async with async_playwright() as pw:
            browser = await launch_browser(pw, settings)
            try:
                with local_site(source / "react" / "dist") as origin:
                    context = await browser.new_context(device_scale_factor=1, reduced_motion="reduce", service_workers="block")
                    async def only_local(route):
                        if route.request.url.startswith(origin + "/"):
                            await route.continue_()
                        else:
                            result["externalRequests"].append(route.request.url)
                            await route.abort()
                    await context.route("**/*", only_local)
                    await context.route_web_socket("**/*", lambda ws: ws.close())
                    for item in ir["pages"]:
                        for width in (1440, 1024, 768, 540, 390):
                            page = await context.new_page()
                            await page.set_viewport_size({"width": width, "height": 900})
                            page.on("pageerror", lambda e: result["browserErrors"].append(str(e)))
                            response = await page.goto(origin + "/" + page_file(item), wait_until="networkidle")
                            await page.locator("h1").wait_for()
                            await settle(page)
                            image = output / f"{item['key']}-{width}-react.png"
                            await screenshot(page, image)
                            comparison = compare_images(source / "evidence" / f"{item['key']}-{width}-source.png", image, output / f"{item['key']}-{width}-react-diff.png")
                            result["reactComparisons"].append(dict(page=item["key"], width=width, **comparison))
                            check(f"React {item['route']} {width}px loaded", response is not None and response.status == 200)
                            check(f"React {item['route']} {width}px local images", await page.locator("img").evaluate_all("xs => xs.every(x => x.complete && x.naturalWidth > 0)"))
                            if item["key"] == "p0" and width == 390:
                                button = page.locator("button[aria-controls='mobile-menu']")
                                await button.click()
                                await expect(page.locator("#mobile-menu")).to_be_visible()
                                check("React mobile menu opens", True)
                                await button.press("Escape")
                                await expect(page.locator("#mobile-menu")).to_be_hidden()
                                check("React mobile menu closes with Escape", True)
                                await page.locator("details summary").first.click()
                                check("React native accordion opens", await page.locator("details").first.evaluate("e => e.open"))
                            await page.close()
                    await context.close()
                check("All React/source visual comparisons pass", len(result["reactComparisons"]) == len(ir["pages"]) * 5 and all(c["passed"] for c in result["reactComparisons"]))
                check("React has no external runtime requests", not result["externalRequests"])
                with http_worker(settings) as origin:
                    # Only the authored studio is opened here. Playwright 1.57's
                    # service_workers='block' injects navigator.serviceWorker access
                    # into every frame, throwing on opaque sandbox origins. Use the
                    # normal browser context for this integration test. The actual
                    # preview CSP and sandbox remain unchanged, and are tested below.
                    # Production untrusted capture STILL uses service_workers='block'.
                    context = await browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
                    page = await context.new_page()
                    page.on("pageerror", lambda e: result["browserErrors"].append(str(e)))
                    unauth = await context.request.get(origin + "/api/jobs")
                    check("Actual HTTP API rejects missing key", unauth.status == 401)
                    await page.goto(origin, wait_until="networkidle")
                    await page.locator("#workspace-button").click()
                    await page.locator("#access-key").fill(settings.api_key)
                    await page.locator("#access-form button[type=submit]").click()
                    await page.locator(f"[data-job='{copy['id']}']").click()
                    await page.locator(".preview-toolbar").wait_for()
                    check("Authenticated studio loads real saved conversion", await page.locator("h1").inner_text() == "Forma Studio")
                    await page.locator("#preview-mode").select_option("live")
                    iframe = page.locator("iframe[title='Sandboxed exported website']")
                    check("Preview does not grant same-origin privilege", await iframe.get_attribute("sandbox") == "allow-scripts")
                    frame = page.frame_locator("iframe[title='Sandboxed exported website']")
                    await frame.locator("h1").wait_for()
                    await frame.locator("img").first.wait_for(state="visible")
                    check("Sandboxed iframe loads its image", await frame.locator("img").first.evaluate("e => e.complete && e.naturalWidth > 0"))
                    check("Preview cannot access parent document", await frame.locator("body").evaluate("() => { try { void parent.document; return false; } catch (e) { return e.name === 'SecurityError'; } }"))
                    check("Preview cannot access service worker API", await frame.locator("body").evaluate("() => { try { return !navigator.serviceWorker; } catch (e) { return e.name === 'SecurityError'; } }"))
                    await frame.locator("details summary").first.click()
                    check("Iframe native disclosure works", await frame.locator("details").first.evaluate("e => e.open"))
                    await page.locator("[data-width='390']").click()
                    frame = page.frame_locator("iframe")
                    await frame.locator("button[aria-controls='mobile-menu']").click()
                    await expect(frame.locator("#mobile-menu")).to_be_visible()
                    check("Iframe script adapter opens mobile menu", True)
                    await page.locator("[data-tab='source']").click()
                    await page.locator("[data-file='src/components/Hero.tsx']").click()
                    # Clicking starts an asynchronous fetch. Assert the eventual
                    # DOM state, not the stale content immediately after the click.
                    await expect(page.locator(".code-scroll code")).to_contain_text("function Hero", timeout=10000)
                    check("Live source browser reads generated React", True)
                    base = origin + "/api/jobs/" + copy["id"]
                    auth = {"Authorization": "Bearer " + settings.api_key}
                    before = await (await context.request.get(base, headers=auth)).json()
                    ticket = before["ticket"]
                    preview = await context.request.get(origin + f"/preview/{copy['id']}/{ticket}/index.html")
                    csp = preview.headers.get("content-security-policy", "")
                    check("Preview CSP preserves sandbox and blocks outbound connections", "sandbox allow-scripts;" in csp and "connect-src 'none'" in csp and "form-action 'none'" in csp and "allow-same-origin" not in csp)
                    await page.locator("[data-tab='content']").click()
                    field_id = next(k for k, v in ir["texts"].items() if "A little different." in v)
                    field = page.locator(f"textarea[data-content='{field_id}']")
                    await field.fill("A genuinely editable beginning.")
                    await page.locator("#save-content").click()
                    await page.locator(".progress-card").wait_for()
                    check("Old signed preview blocked during rebuild", (await context.request.get(origin + f"/preview/{copy['id']}/{ticket}/index.html")).status == 409)
                    await page.locator(".project-workbench").wait_for(timeout=180000)
                    await expect(page.locator(f"textarea[data-content='{field_id}']")).to_have_value("A genuinely editable beginning.", timeout=10000)
                    check("Editor refreshes persisted text after rebuild", True)
                    await page.locator("[data-tab='source']").click()
                    await page.locator("[data-file='src/content/site.json']").click()
                    await expect(page.locator(".code-scroll code")).to_contain_text("A genuinely editable beginning.", timeout=10000)
                    check("Source viewer refreshes regenerated content", True)
                    after = await (await context.request.get(base, headers=auth)).json()
                    check("Real worker regenerates revision one", after["status"] == "completed" and after["revision"] == 1)
                    check("Edited page produces new visual evidence", any(c["changedPixels"] > 0 for c in after["report"]["comparisons"]))
                    check("Old signed preview revoked after rebuild", (await context.request.get(origin + f"/preview/{copy['id']}/{ticket}/index.html")).status == 403)
                    for target in ("react", "html"):
                        async with page.expect_download() as download_info:
                            await page.locator(f"#download-{target}").click()
                        download = await download_info.value
                        zip_path = output / f"edited-{target}.zip"
                        await download.save_as(zip_path)
                        with zipfile.ZipFile(zip_path) as archive:
                            text = archive.read("src/content/site.json" if target == "react" else "index.html").decode()
                        check(f"Browser {target} download contains regenerated content", "A genuinely editable beginning." in text)
                    await page.screenshot(path=str(output / "studio-after-edit.png"), full_page=True)
                    await context.close()
                check("No uncaught browser errors", not result["browserErrors"])
                result["passed"] = True
            finally:
                await browser.close()
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    finally:
        (output / "acceptance.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2), flush=True)
    return result["passed"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", default="fixture-result.json", type=Path)
    parser.add_argument("--data", default=".frameport-ci", type=Path)
    parser.add_argument("--output", default=".frameport-acceptance", type=Path)
    args = parser.parse_args()
    if not asyncio.run(run(args.job, args.data, args.output.resolve())):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
