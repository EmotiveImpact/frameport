import argparse,json,asyncio
from pathlib import Path
from playwright.async_api import async_playwright, expect

async def main():
    a=argparse.ArgumentParser();a.add_argument('--preview',required=True);a.add_argument('--output',required=True);a.add_argument('--chromium',default=None);args=a.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    html=Path(args.preview).read_text()
    checks=[];errors=[]
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(executable_path=args.chromium,headless=True)
        for width,height in [(1440,1100),(1024,1000),(768,1000),(390,844)]:
            print('Viewport',width,flush=True)
            page=await browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
            page.on('pageerror',lambda e:errors.append(str(e)))
            await page.set_content(html,wait_until='load');await page.wait_for_timeout(650)
            assert await page.locator('h1').count()
            overflow=await page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
            checks.append({'view':'overview','width':width,'passed':not overflow,'horizontalOverflow':overflow})
            await page.screenshot(path=str(out/f'overview-{width}.png'),full_page=True)
            button=page.locator('[data-job]').first
            await button.click();await page.wait_for_timeout(500)
            assert await page.locator('.workbench,.preview-panel,.preview-toolbar').count()
            overflow=await page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
            checks.append({'view':'workspace','width':width,'passed':not overflow,'horizontalOverflow':overflow})
            await page.screenshot(path=str(out/f'workspace-{width}.png'),full_page=True)
            for tab in ['source','content','report']:
                print('Tab',width,tab,flush=True)
                await page.locator(f'[data-tab="{tab}"]').click();await page.wait_for_timeout(200)
                if tab == 'source': await expect(page.locator('.code-scroll code')).to_contain_text('function Hero')
                if tab == 'content': await expect(page.locator('textarea[data-content]').first).to_be_visible()
                if tab == 'report': await expect(page.locator('.matrix')).to_be_visible()
                overflow=await page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
                checks.append({'view':tab,'width':width,'passed':not overflow,'horizontalOverflow':overflow})
                if width in (1440,390):await page.screenshot(path=str(out/f'{tab}-{width}.png'),full_page=True)
            await page.close()
        await browser.close()
    result={'mode':'offline portable preview UI; no browser HTTP navigation or live API integration','checks':checks,'consoleErrors':errors}
    (out/'preview-checks.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    if errors or not all(c['passed'] for c in checks):raise SystemExit(1)
if __name__=='__main__':asyncio.run(main())
