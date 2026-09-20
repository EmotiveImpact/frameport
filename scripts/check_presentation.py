"""Real HTTP typography/art-direction checks using the actual authored fixture.

These complement the existing animation/lifecycle and conversion acceptance
suites. No public site is visited and no conversion fidelity is inferred here.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import re
from pathlib import Path
import shutil
from PIL import Image
from playwright.async_api import async_playwright, expect
from frameport.config import Settings
from frameport.store import Store
from scripts.check_acceptance import http_worker, load_fixture


async def run(job_file: Path, data: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    result = {'mode': 'real-http-software-webgl', 'scope': 'Authored Frameport presentation; not a live Framer benchmark', 'checks': [], 'errors': [], 'passed': False}

    def check(name, ok):
        result['checks'].append({'name': name, 'passed': bool(ok)})
        if not ok:
            raise AssertionError(name)

    async def weight(page, selector, minimum, name):
        locator = page.locator(selector).first
        # Source selection can replace the DOM after its fetch. Assert the
        # settled CSS on a re-resolving locator, not a transient detached node.
        allowed = re.compile('^(?:' + '|'.join(str(w) for w in range(minimum, 1001, 100)) + ')$')
        await expect(locator).to_have_css('font-weight', allowed, timeout=10000)
        check(name, True)

    try:
        fixture, source = load_fixture(job_file, data)
        settings = Settings(data=output / 'private-workspace')
        store = Store(settings.data)
        job = store.create(fixture['request'])
        shutil.copytree(source, settings.data / 'jobs' / job['id'], ignore=shutil.ignore_patterns('node_modules', 'dist', 'package-lock.json'))
        store.update(job['id'], status='completed', stage='Complete', progress=100, report=fixture['report'])
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, executable_path=settings.chromium_path, chromium_sandbox=not settings.unsandboxed_test_browser, args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
            try:
                with http_worker(settings) as origin:
                    context = await browser.new_context(viewport={'width': 1440, 'height': 950}, device_scale_factor=1, reduced_motion='reduce')
                    page = await context.new_page()
                    page.on('pageerror', lambda e: result['errors'].append(str(e)))
                    for width in (1440, 768, 390, 320):
                        await page.set_viewport_size({'width': width, 'height': 950})
                        await page.goto(origin, wait_until='networkidle')
                        await expect(page.locator('.hero-visual')).to_have_attribute('data-renderer', 'webgl')
                        await expect(page.locator('.hero-visual')).to_have_attribute('data-motion', 'reduced')
                        await weight(page, '#hero-title', 600, f'{width}px semibold hero')
                        await weight(page, '.hero-copy p', 500, f'{width}px medium body copy')
                        await weight(page, '.main-nav button', 600, f'{width}px stronger navigation')
                        await weight(page, '#start-converting', 600, f'{width}px stronger primary action')
                        check(f'{width}px pure-black canvas', await page.evaluate("getComputedStyle(document.documentElement).backgroundColor === 'rgb(0, 0, 0)'"))
                        check(f'{width}px no page overflow', await page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
                        if width <= 390:
                            check(f'{width}px heading retains three readable lines', await page.locator('#hero-title').evaluate('e => e.getBoundingClientRect().height / parseFloat(getComputedStyle(e).lineHeight) < 3.2'))
                        check(f'{width}px heading is not clipped', await page.locator('.welcome').evaluate("e => {const h=e.querySelector('#hero-title').getBoundingClientRect(), r=e.getBoundingClientRect(); return e.scrollLeft===0 && h.left>=r.left && h.right<=r.right;}"))
                        if width == 1440:
                            check('Artwork is large and intentionally cropped at right', await page.evaluate("() => {const a=document.querySelector('.hero-visual').getBoundingClientRect(),h=document.querySelector('.welcome').getBoundingClientRect();return a.height>=700 && a.right>h.right && h.right<=innerWidth+1;}"))
                        await page.screenshot(path=str(output / f'home-{width}.png'), full_page=False)
                        if width == 1440:
                            with Image.open(output / f'home-{width}.png') as image:
                                art = image.convert('RGB').crop((720, 120, 1440, 690))
                                histogram = art.convert('L').histogram()
                                ratio = sum(histogram[85:]) / (art.width * art.height)
                                result['visibleArtworkBrightFraction'] = ratio
                                check('Visible silver surface is more than a faint hairline', ratio > 0.009)
                        await page.locator(f"[data-job='{job['id']}']").click()
                        await page.locator('.preview-toolbar').wait_for()
                        await weight(page, '.project-heading h1', 600, f'{width}px semibold project heading')
                        for tab in ('source', 'content', 'report'):
                            await page.locator(f"[data-tab='{tab}']").click()
                            if tab == 'source':
                                await page.locator("[data-file='src/components/Hero.tsx']").click()
                                await expect(page.locator('.code-scroll code')).to_contain_text('function Hero')
                                await weight(page, '.code-scroll pre', 500, f'{width}px readable code weight')
                                check(f'{width}px code is at least 12px', await page.locator('.code-scroll pre').evaluate('e => parseFloat(getComputedStyle(e).fontSize)>=12'))
                            elif tab == 'content':
                                await page.locator('textarea[data-content]').first.wait_for()
                                await weight(page, '.content-intro h3', 600, f'{width}px semibold editor heading')
                                await weight(page, 'textarea[data-content]', 500, f'{width}px medium editable text')
                            else:
                                await weight(page, '.report-header h2', 600, f'{width}px semibold verification heading')
                            check(f'{width}px {tab} fits the viewport', await page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
                            if width in (1440, 390):
                                await page.screenshot(path=str(output / f'{tab}-{width}.png'), full_page=True)
                        await page.locator(".main-nav [data-view='docs']").click()
                        await weight(page, '.doc-card h2', 600, f'{width}px semibold documentation heading')
                        check(f'{width}px docs fit the viewport', await page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
                    await context.close()
                    check('No uncaught browser errors', not result['errors'])
                    result['passed'] = True
            finally:
                await browser.close()
    except Exception as error:
        result['error'] = f'{type(error).__name__}: {error}'
    finally:
        (output / 'presentation-checks.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2), flush=True)
    return result['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', type=Path, default=Path('fixture-result.json'))
    parser.add_argument('--data', type=Path, default=Path('.frameport-ci'))
    parser.add_argument('--output', type=Path, default=Path('artifacts/presentation'))
    args = parser.parse_args()
    if not asyncio.run(run(args.job, args.data, args.output.resolve())):
        raise SystemExit(1)
