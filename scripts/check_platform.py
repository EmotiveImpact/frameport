"""Actual gateway -> persistent API -> subprocess worker acceptance.

Only the original Forma fixture is converted. No offline document adapter, fake
API, pre-completed job or fabricated render report is used by this test.
"""
from __future__ import annotations
import argparse
import asyncio
from contextlib import contextmanager
import json
from pathlib import Path
import secrets
import socket
import threading
import time
import zipfile
import uvicorn
from playwright.async_api import async_playwright, expect
from frameport.app import create_app
from frameport.config import Settings
from frameport.gateway import create_gateway
from frameport.store import Store


def listening_socket(port=0):
    sock=socket.socket();sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    sock.bind(('127.0.0.1',port));return sock

@contextmanager
def server(app,sock):
    origin=f'http://127.0.0.1:{sock.getsockname()[1]}'
    instance=uvicorn.Server(uvicorn.Config(app,log_level='warning'))
    thread=threading.Thread(target=instance.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    try:
        deadline=time.monotonic()+20
        while not instance.started:
            if not thread.is_alive() or time.monotonic()>deadline:raise RuntimeError('Server did not start')
            time.sleep(.03)
        yield origin
    finally:
        instance.should_exit=True;thread.join(timeout=20);sock.close()

async def run(output):
    output.mkdir(parents=True,exist_ok=True)
    checks=[];errors=[];result={'scope':'Real HTTP gateway, cookie session, durable queue and subprocess conversion of authored Forma fixture', 'checks':checks,'errors':errors,'passed':False}
    def check(name,ok):
        checks.append({'name':name,'passed':bool(ok)})
        if not ok:raise AssertionError(name)
    gateway_sock=listening_socket();worker_sock=listening_socket()
    gateway_origin=f'http://127.0.0.1:{gateway_sock.getsockname()[1]}'
    settings=Settings(data=output/'private-workspace',api_key=secrets.token_urlsafe(32),public_origin=gateway_origin)
    try:
        with server(create_app(settings),worker_sock) as worker_origin, server(create_gateway(worker_origin,local_test=True),gateway_sock) as origin:
            async with async_playwright() as pw:
                browser=await pw.chromium.launch(headless=True,executable_path=settings.chromium_path,chromium_sandbox=not settings.unsandboxed_test_browser)
                try:
                    context=await browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True,reduced_motion='reduce')
                    page=await context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                    await page.goto(origin+'/projects',wait_until='networkidle')
                    await page.locator('#platform-login').wait_for()
                    check('Direct project route requires sign in',page.url.endswith('/projects'))
                    await page.locator('#login-key').fill(settings.api_key)
                    await page.locator('#platform-login button').click()
                    await page.locator('#run-demo').wait_for()
                    check('Workspace is empty rather than simulated',await page.locator('[data-job]').count()==0)
                    cookie=next(c for c in await context.cookies() if c['name']=='frameport_session')
                    check('Session cookie is HTTP-only',cookie['httpOnly'] and cookie['sameSite']=='Strict')
                    await page.reload(wait_until='networkidle');await page.locator('#run-demo').wait_for()
                    check('Authentication survives a page reload',await page.locator('#platform-login').count()==0)
                    await page.locator('#run-demo').click()
                    await page.wait_for_url('**/projects/*/review')
                    await page.locator('.project-workbench').wait_for(timeout=180000)
                    ident=page.url.split('/projects/')[1].split('/')[0]
                    result['projectId']=ident
                    base=origin+'/api/jobs/'+ident
                    record=await (await context.request.get(base)).json()
                    check('Actual subprocess completes the sample conversion',record['status']=='completed' and record.get('attempts',0)==1)
                    check('Two real pages were captured',len(record['report']['pages'])==2)
                    check('Ten source/HTML comparisons passed',len(record['report']['comparisons'])==10 and all(c['passed'] for c in record['report']['comparisons']))
                    check('No offline substitute is in the report',record['report'].get('execution',{}).get('mode')!='offline-document-harness')
                    await page.screenshot(path=str(output/'project-review.png'),full_page=True)
                    await page.locator('#rename-project').click();await page.locator('#rename-input').fill('Frameport platform trial')
                    await page.locator('#rename-form .primary').click()
                    await expect(page.locator('.project-heading h1')).to_have_text('Frameport platform trial')
                    check('Renamed project is written to the durable store',Store(settings.data).get(ident)['request']['name']=='Frameport platform trial')
                    await page.locator('[data-tab=source]').click()
                    await page.locator('[data-file="src/components/Hero.tsx"]').click()
                    await expect(page.locator('.code-scroll code')).to_contain_text('function Hero')
                    check('Source tab has its own address','/source' in page.url and 'file=' in page.url)
                    await page.reload(wait_until='networkidle')
                    await expect(page.locator('.code-scroll code')).to_contain_text('function Hero')
                    check('Source deep link restores file after reload',True)
                    await page.locator('[data-tab=report]').click();await page.wait_for_url('**/verify')
                    await page.go_back();await expect(page.locator('.code-scroll code')).to_contain_text('function Hero')
                    check('Browser back restores the source workspace',True)
                    await page.goto(origin+'/projects/'+ident+'/content',wait_until='networkidle')
                    fields=await (await context.request.get(base+'/content')).json()
                    field=next(f for f in fields if 'A little different.' in f['text'])
                    await page.locator(f'textarea[data-content="{field["id"]}"]').fill('Built to keep moving.')
                    await page.locator('#save-content').click()
                    await page.locator('.progress-card').wait_for()
                    await page.locator('.project-workbench').wait_for(timeout=180000)
                    await expect(page.locator(f'textarea[data-content="{field["id"]}"]')).to_have_value('Built to keep moving.')
                    check('Content edit executes in a separate worker and reloads',True)
                    revision=await (await context.request.get(base)).json()
                    check('Revision one is durable',revision['revision']==1 and Store(settings.data).get(ident)['revision']==1)
                    old=await context.request.post(base+'/edits',data=json.dumps({'expected_revision':0,'patches':[{'id':field['id'],'text':'Stale overwrite'}]}),headers={'Content-Type':'application/json'})
                    check('A stale editor cannot overwrite the new revision',old.status==409)
                    summaries=await (await context.request.get(base+'/revisions')).json()
                    check('Revision history is persisted',[r['revision'] for r in summaries]==[1,0])
                    await page.locator('[data-tab=export]').click();await page.wait_for_url('**/export')
                    await page.locator('.export-grid').wait_for()
                    for target in ('react','html'):
                        async with page.expect_download() as info:await page.locator(f'[data-export={target}]').click()
                        download=await info.value;archive=output/f'{target}-platform.zip';await download.save_as(archive)
                        with zipfile.ZipFile(archive) as z:content=z.read('src/content/site.json' if target=='react' else 'index.html').decode()
                        check(f'{target} download contains the saved edit','Built to keep moving.' in content)
                    await page.screenshot(path=str(output/'project-export.png'),full_page=True)
                    await page.goto(origin+'/projects',wait_until='networkidle');await page.locator(f'[data-job="{ident}"]').wait_for()
                    check('Project library retrieves persisted project',True)
                    await page.screenshot(path=str(output/'project-library.png'),full_page=True)
                    await page.goto(origin+'/settings',wait_until='networkidle');await page.locator('.service-grid').wait_for()
                    health=await (await context.request.get(origin+'/api/health')).json()
                    check('Gateway readiness comes from the real worker',health['canConvert'] and health['deployment']=='gateway')
                    await page.screenshot(path=str(output/'workspace-settings.png'),full_page=True)
                    for width in (768,390,320):
                        await page.set_viewport_size({'width':width,'height':900})
                        for path in ('/projects','/convert','/settings',f'/projects/{ident}/source',f'/projects/{ident}/export'):
                            await page.goto(origin+path,wait_until='networkidle');await page.wait_for_timeout(150)
                            check(f'No horizontal overflow {path} {width}',await page.evaluate('document.documentElement.scrollWidth<=innerWidth+2'))
                        if width==390:await page.screenshot(path=str(output/'mobile-export.png'),full_page=True)
                    await page.goto(origin+'/settings',wait_until='networkidle');await page.locator('#logout-workspace').click()
                    await page.locator('#platform-login').wait_for()
                    check('Sign out revokes the session',(await context.request.get(base)).status==401)
                    await context.close()
                    check('No uncaught browser errors',not errors)
                    result['passed']=True
                finally:await browser.close()
        # A new API instance with the same disk has not silently discarded projects.
        check('Project persists after both HTTP services shut down',Store(settings.data).get(result['projectId'])['request']['name']=='Frameport platform trial')
    except Exception as error:
        result['passed']=False
        result['error']=f'{type(error).__name__}: {error}'
    finally:
        (output/'platform.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2),flush=True)
    return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('artifacts/platform'));a=p.parse_args()
    if not asyncio.run(run(a.output.resolve())):raise SystemExit(1)
