import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import time
import httpx
import pytest
from fastapi.testclient import TestClient
from frameport.app import create_app
from frameport.config import Settings, env_int
from frameport.gateway import create_gateway, normalise_origin
from frameport.platform_store import Conflict, QueueFull
from frameport.store import Store
from frameport.worker import Supervisor, worker_environment

KEY='private-workspace-test-key-1234567890'

@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Settings(data=tmp_path,api_key=KEY,allowed_hosts=('testserver',),workers=0)))

def completed(client):
    store=client.app.state.store
    job=store.create({'name':'Original','url':'https://example.com','permission':True,'demo':False,'crawl':False,'max_pages':1,'format':'both','bridge':None})
    root=client.app.state.settings.data/'jobs'/job['id'];root.mkdir(parents=True)
    (root/'COMPLETE').write_text('complete')
    (root/'model.json').write_text(json.dumps({'texts':{'p0-text':'Hello'}}))
    (root/'html.zip').write_bytes(b'html');(root/'react.zip').write_bytes(b'react')
    return store.update(job['id'],status='completed',report={'pages':[{}],'visualPassed':True})

def test_blank_numeric_environment(monkeypatch):
    monkeypatch.setenv('FRAMEPORT_RETENTION_DAYS','');assert Settings().retention_days==7
    monkeypatch.setenv('FRAMEPORT_RETENTION_DAYS','x');assert Settings().retention_days==7
    monkeypatch.setenv('FRAMEPORT_RETENTION_DAYS','999');assert Settings().retention_days==30

def test_login_cookie_is_http_only_and_persists(client):
    assert client.get('/api/session').json()['authenticated'] is False
    response=client.post('/api/session',json={'key':KEY})
    assert response.status_code==200
    assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=strict' in response.headers['set-cookie']
    assert client.get('/api/jobs').status_code==200
    settings=client.app.state.settings
    restarted=TestClient(create_app(settings));restarted.cookies.update(client.cookies)
    assert restarted.get('/api/session').json()['authenticated'] is True
    token=client.cookies['frameport_session']
    assert token not in settings.data.joinpath('jobs.sqlite3').read_bytes().decode('latin1')
    assert client.request('DELETE','/api/session',json={}).status_code==200
    assert client.get('/api/jobs').status_code==401
    assert restarted.get('/api/jobs').status_code==401

def test_key_rotation_revokes_cookie(client):
    client.post('/api/session',json={'key':KEY})
    settings=client.app.state.settings
    other=TestClient(create_app(Settings(data=settings.data,api_key='different-secret',allowed_hosts=('testserver',))))
    other.cookies.update(client.cookies);assert other.get('/api/jobs').status_code==401

def test_login_rate_limited(client):
    for _ in range(20):assert client.post('/api/session',json={'key':'wrong'}).status_code==401
    assert client.post('/api/session',json={'key':KEY}).status_code==429

def test_session_secure_cookie_when_behind_https(tmp_path):
    c=TestClient(create_app(Settings(data=tmp_path,api_key=KEY,public_origin='https://frameport.vercel.app',allowed_hosts=('testserver',))))
    r=c.post('/api/session',json={'key':KEY});assert '; Secure' in r.headers['set-cookie']

def test_private_routes_are_not_public_data(client):
    assert client.get('/projects').status_code==200
    assert client.get('/api/projects').status_code==401
    assert client.get('/api/jobs').status_code==401

def test_persistent_service_readiness_not_invented(client):
    h=client.get('/api/health').json();assert h['canConvert'] is False and h['worker']=='offline'
    assert client.get('/api/ready').status_code==503

@pytest.mark.parametrize('path',['/','/convert','/projects','/docs','/settings','/login', '/projects/'+'a'*32,
    *['/projects/'+'a'*32+'/'+tab for tab in ('review','source','content','verify','export')]])
def test_real_document_routes(client,path):
    r=client.get(path);assert r.status_code==200 and '/static/platform.css' in r.text

@pytest.mark.parametrize('path',['/api/nonsense','/static/nonsense.js','/projects/nope/source','/projects/'+'a'*32+'/unknown','/something'])
def test_unknown_paths_not_masked_by_spa(client,path):assert client.get(path).status_code==404

def test_idempotent_submission_and_atomic_bound(tmp_path):
    s=Store(tmp_path)
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs=list(pool.map(lambda _:Store(tmp_path).enqueue({'demo':True},key='same'),range(10)))
    assert len({j['id'] for j in jobs})==1 and len(s.list())==1
    with pytest.raises(Conflict):s.enqueue({'demo':False},key='same')
    s.enqueue({'second':True},limit=2)
    with pytest.raises(QueueFull):s.enqueue({'third':True},limit=2)

def test_queued_jobs_survive_reopen_and_claim_once(tmp_path):
    s=Store(tmp_path);job=s.enqueue({'demo':True})
    assert Store(tmp_path).get(job['id'])['status']=='queued'
    with ThreadPoolExecutor(max_workers=5) as pool:
        results=list(pool.map(lambda _:Store(tmp_path).claim_next(),range(5)))
    assert len([r for r in results if r])==1
    s.interrupt(job['id']);assert s.get(job['id'])['status']=='queued'
    s.claim_next();s.interrupt(job['id']);assert s.get(job['id'])['status']=='failed'

def test_competing_edits_have_one_winner(client):
    job=completed(client);s=client.app.state.store
    def change(_):
        try:return s.queue_edits(job['id'],[{'id':'p0-text','text':'Next'}],0)['revision']
        except Conflict:return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(change,range(2)))
    assert sorted(map(str,results))==['1','conflict']
    assert s.revisions(job['id'])[0]['revision']==0

def test_stale_editor_rejected_and_revision_invalidates_links(client):
    job=completed(client);base='/api/jobs/'+job['id'];auth={'Authorization':'Bearer '+KEY}
    link=client.get(base+'/export-links',headers=auth).json()['react']['url']
    assert client.get(link).status_code==200
    assert client.get(link.replace('/react','/html')).status_code==403
    assert client.post(base+'/edits',headers=auth,json={'expected_revision':2,'patches':[{'id':'p0-text','text':'Next'}]}).status_code==409
    assert client.post(base+'/edits',headers=auth,json={'expected_revision':0,'patches':[{'id':'p0-text','text':'Next'}]}).status_code==202
    assert client.get(link).status_code==409

def test_rename_and_delete_persist(client):
    job=completed(client);base='/api/jobs/'+job['id'];auth={'Authorization':'Bearer '+KEY}
    assert client.patch(base,headers=auth,json={'name':'  My project  '}).json()['request']['name']=='My project'
    assert Store(client.app.state.settings.data).get(job['id'])['request']['name']=='My project'
    assert client.patch(base,headers=auth,json={'name':'   '}).status_code==422
    assert client.request('DELETE',base,headers=auth,json={}).status_code==200
    assert Store(client.app.state.settings.data).get(job['id']) is None

def test_worker_does_not_inherit_secrets(tmp_path,monkeypatch):
    monkeypatch.setenv('FRAMEPORT_API_KEY','TOP_SECRET');monkeypatch.setenv('AWS_SECRET_ACCESS_KEY','NOT_FOR_BROWSER')
    env=worker_environment(Settings(data=tmp_path,api_key=KEY))
    assert 'FRAMEPORT_API_KEY' not in env and 'AWS_SECRET_ACCESS_KEY' not in env
    assert KEY not in json.dumps(env) and 'TOP_SECRET' not in json.dumps(env)

def test_worker_process_can_be_terminated(tmp_path):
    async def run():
        supervisor=Supervisor(Store(tmp_path),Settings(data=tmp_path))
        proc=await asyncio.create_subprocess_exec(sys.executable,'-c','import time; time.sleep(60)',start_new_session=os.name=='posix')
        await supervisor.stop_process(proc);assert proc.returncode is not None
    asyncio.run(run())

@pytest.mark.parametrize('url',['http://worker.example','https://user:secret@worker.example','https://worker.example/path','https://worker.example?x=1','https://worker.example#x','https://127.0.0.1','https://machine.local','https://worker.example:3000'])
def test_gateway_rejects_invalid_upstream(url):
    with pytest.raises(ValueError):normalise_origin(url)

def test_gateway_has_no_storage_side_effects(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path);gateway=create_gateway('');c=TestClient(gateway)
    assert c.get('/').status_code==200
    h=c.get('/api/health').json();assert h['canConvert'] is False and h['worker']=='unconfigured'
    assert c.get('/api/ready').status_code==503
    assert c.get('/api/jobs').status_code==503
    assert c.post('/api/jobs',json={'demo':True,'permission':True}).status_code==503
    assert not list(tmp_path.iterdir())

def test_gateway_forwards_session_without_privilege(tmp_path):
    requests=[]
    def transport(request):
        requests.append(request)
        if request.url.path=='/api/health':return httpx.Response(200,json={'worker':'available','canConvert':True,'storage':'persistent-volume','authRequired':True})
        if request.url.path=='/api/jobs/project/export-links':return httpx.Response(200,json={'react':{'url':'/download/id/token/react'}})
        return httpx.Response(200,json={'ok':True},headers={'set-cookie':'frameport_session=opaque; HttpOnly; Path=/; SameSite=strict'})
    c=TestClient(create_gateway('https://worker.example',transport=httpx.MockTransport(transport)))
    h=c.get('/api/health').json();assert h['canConvert'] is True and h['storage']=='persistent-volume'
    assert c.get('/api/ready').status_code==200
    c.cookies.set('frameport_session','known')
    r=c.post('/api/session',json={'key':'supplied'},headers={'Origin':'http://testserver','X-Forwarded-Host':'attacker','Authorization':'Bearer test'})
    assert r.status_code==200
    request=requests[-1];assert request.headers.get('authorization')=='Bearer test'
    assert request.headers['cookie']=='frameport_session=known'
    assert 'x-forwarded-host' not in request.headers and request.url.host=='worker.example'
    assert 'HttpOnly' in r.headers['set-cookie']
    assert c.get('/api/jobs/project/export-links').json()['react']['url'].startswith('https://worker.example/download/')
    assert c.post('/api/jobs',json={},headers={'Origin':'https://attacker'}).status_code==403
    assert c.post('/api/jobs',content='x',headers={'content-type':'text/plain'}).status_code==415
    assert c.post('/api/jobs',content=b'x'*1_200_001,headers={'content-type':'application/json'}).status_code==413

@pytest.mark.parametrize('payload',[{'worker':'available'}, {'worker':'offline','canConvert':True}])
def test_gateway_does_not_promote_false_readiness(payload):
    c=TestClient(create_gateway('https://worker.example',transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload))))
    assert c.get('/api/health').json()['canConvert'] is False

def test_gateway_offline_upstream_is_visible():
    def broken(request):raise httpx.ConnectError('worker offline')
    c=TestClient(create_gateway('https://worker.example',transport=httpx.MockTransport(broken)))
    assert c.get('/api/health').json()['worker']=='offline'
    assert c.post('/api/jobs',json={}).json()['code']=='worker-offline'


def test_unicode_credentials_fail_cleanly(client):
    assert client.post('/api/session',json={'key':'wrong-🔑'}).status_code==401

def test_gateway_malformed_health_is_offline():
    c=TestClient(create_gateway('https://worker.example',transport=httpx.MockTransport(lambda r:httpx.Response(200,json=[]))))
    assert c.get('/api/health').json()['worker']=='offline'
