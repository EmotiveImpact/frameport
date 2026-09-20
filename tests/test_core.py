import asyncio
import json
import socket
from pathlib import Path
from unittest.mock import patch
import pytest
from PIL import Image
from fastapi import HTTPException
from frameport.app import safe_path,create_app
from frameport.config import Settings
from frameport.engine.network import normalise_url,public_ip,SafeFetcher,NetworkError,Response
from frameport.engine.assets import AssetCollector,safe_svg
from frameport.engine.compiler import safe_link,clean_tree,html_attrs,to_html,jsx_attrs,react_style,generate,prepare_ir,attrs_for
from frameport.engine.validate import compare_images,local_site
from frameport.models import ConvertRequest,BridgeManifest
from frameport.store import Store
from fastapi.testclient import TestClient

@pytest.mark.parametrize('url',["file:///etc/passwd","javascript:alert(1)","http://a:pw@example.com","ftp://example.com","https://example.com:3000","https://example.com/\nhi","http://evil\\example.com"])
def test_bad_urls(url):
    with pytest.raises(NetworkError): normalise_url(url)

@pytest.mark.parametrize('ip',['127.0.0.1','0.0.0.0','10.1.2.3','192.168.1.4','172.16.0.1','169.254.169.254','100.64.0.1','::1','::','fc00::1','fe80::1','::ffff:127.0.0.1','224.0.0.1','2001:db8::1'])
def test_private_ips(ip):assert not public_ip(ip)

@pytest.mark.parametrize('ip',['1.1.1.1','8.8.8.8','2606:4700:4700::1111'])
def test_public_ips(ip):assert public_ip(ip)

def test_normalise():assert normalise_url('Example.COM/a#x')=='https://example.com/a'

def test_mixed_dns_blocks():
    answers=[(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,443)) for ip in ['8.8.8.8','127.0.0.1']]
    with patch('socket.getaddrinfo',return_value=answers),pytest.raises(NetworkError):SafeFetcher().target('https://example.com')

def test_pinned_dns_result():
    with patch('socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('8.8.8.8',443))]):
        _,ip=SafeFetcher().target('https://example.com');assert ip=='8.8.8.8'

def test_internal_exception_exact():
    f=SafeFetcher(test_origin='http://127.0.0.1:1234')
    assert f.target('http://127.0.0.1:1234/a')[1]=='127.0.0.1'
    with pytest.raises(NetworkError):f.target('http://127.0.0.1:1235/a')

def test_fetch_local_bounded(tmp_path):
    (tmp_path/'hello.txt').write_text('hello')
    with local_site(tmp_path) as origin:
        f=SafeFetcher(test_origin=origin,max_requests=1)
        assert f.get(origin+'/hello.txt').body==b'hello'
        assert f.get(origin+'/hello.txt').body==b'hello' # cache
        with pytest.raises(NetworkError):f.get(origin+'/missing')
        f.closed=True
        with pytest.raises(NetworkError):f.get(origin+'/hello.txt')

@pytest.mark.parametrize('value',['javascript:alert(1)','java\nscript:alert(1)','data:text/html,hi','file:///etc/passwd','blob:abc','vbscript:x'])
def test_bad_links(value):assert safe_link(value)=='#'

@pytest.mark.parametrize('value',['#work','/about/','../index.html','https://example.com','mailto:a@example.com','tel:+441234'])
def test_safe_links(value):assert safe_link(value)==value

def test_path_traversal(tmp_path):
    (tmp_path/'ok.txt').write_text('ok')
    assert safe_path(tmp_path,'ok.txt').read_text()=='ok'
    for path in ['../elsewhere','/etc/passwd','a\\b','\x00']:
        with pytest.raises(HTTPException):safe_path(tmp_path,path)

def test_pixel_comparison_full_dimensions(tmp_path):
    a=tmp_path/'a.png';b=tmp_path/'b.png';d=tmp_path/'d.png'
    Image.new('RGB',(30,100),(255,255,255)).save(a)
    Image.new('RGB',(30,100),(255,255,255)).save(b)
    r=compare_images(a,b,d);assert r['passed'] and r['totalPixels']==3000
    Image.new('RGB',(30,101),(255,255,255)).save(b)
    assert not compare_images(a,b,d)['passed']
    Image.new('RGB',(30,100),(0,0,0)).save(b)
    assert not compare_images(a,b,d)['passed']

def test_attribute_escaping():
    assert '&quot;' in html_attrs({'title':'" onmouseover="bad'})
    assert 'className=' in jsx_attrs({'class':'hero'})
    assert 'viewBox=' in jsx_attrs({'viewbox':'0 0 100 100'},True)

def test_inline_style():
    value,important=react_style('font-size: 18px; --ink: #333; margin: 0 !important')
    assert json.loads(value)['fontSize']=='18px' and important

def test_store_persistence(tmp_path):
    s=Store(tmp_path);j=s.create({'demo':True});s.event(j['id'],'Capture',20,'Reading')
    assert Store(tmp_path).get(j['id'])['progress']==20
    assert s.get(j['id'])['events'][0]['message']=='Reading'
    s.delete(j['id']);assert s.get(j['id']) is None

def test_manifest_limits():
    v={'schema':'frameport.bridge.v1','publishedUrl':'https://example.com','project':{'name':'A'},'nodes':[]}
    b=BridgeManifest(**v);assert b.model_dump(by_alias=True)['schema']=='frameport.bridge.v1'
    with pytest.raises(ValueError):BridgeManifest(**(v|{'project':{'name':'X'*1_000_001}}))
    with pytest.raises(ValueError):ConvertRequest(permission=True,bridge=v,arbitrary='bad')

@pytest.fixture
def client(tmp_path):
    settings=Settings(data=tmp_path,allowed_hosts=('testserver',),api_key='test-secret-12345678901234567890')
    # No lifespan here: API contract tests intentionally do not launch jobs.
    return TestClient(create_app(settings))

AUTH={'Authorization':'Bearer test-secret-12345678901234567890'}

def test_authentication(client):
    assert client.get('/api/health').status_code==200
    assert client.get('/api/jobs').status_code==401
    assert client.get('/api/jobs',headers=AUTH).status_code==200

def test_permission_required(client):assert client.post('/api/jobs',headers=AUTH,json={'url':'https://example.com'}).status_code==422

def test_cross_origin(client):
    assert client.post('/api/jobs',headers=AUTH|{'Origin':'https://attacker.example'},json={'demo':True,'permission':True}).status_code==403

def test_content_type(client):assert client.post('/api/jobs',headers=AUTH,content='{}').status_code==415

def test_host_check(client):assert client.get('/api/health',headers={'Host':'attacker.example'}).status_code==400

def test_job_and_cancel(client):
    r=client.post('/api/jobs',headers=AUTH,json={'demo':True,'permission':True});assert r.status_code==202
    id=r.json()['id'];assert client.get('/api/jobs/'+id,headers=AUTH).json()['status']=='queued'
    assert client.get('/api/jobs/'+id+'/download/react',headers=AUTH).status_code==409
    assert client.post('/api/jobs/'+id+'/cancel',headers=AUTH,json={}).json()['status']=='cancelled'
    assert client.delete('/api/jobs/'+id,headers=AUTH|{'content-type':'application/json'}).status_code==200
    assert client.get('/api/jobs/'+id,headers=AUTH).status_code==404

def test_manifest_url_mismatch(client):
    m={'schema':'frameport.bridge.v1','publishedUrl':'https://different.example','project':{}}
    assert client.post('/api/jobs',headers=AUTH,json={'url':'https://example.com','permission':True,'bridge':m}).status_code==422

def test_body_bound(client):
    assert client.post('/api/jobs',headers=AUTH|{'content-type':'application/json'},content='x'*1_200_001).status_code==413

def test_no_preview_for_unfinished(client):
    j=client.post('/api/jobs',headers=AUTH,json={'demo':True,'permission':True}).json()
    assert client.get(f"/preview/{j['id']}/bad/index.html").status_code in (403,409)

def test_headers(client):
    r=client.get('/');assert r.status_code==200
    assert "frame-ancestors 'none'" in r.headers['content-security-policy']
    assert r.headers['x-content-type-options']=='nosniff'

def test_svg_removes_executable_content():
    svg=b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script><foreignObject><p>bad</p></foreignObject><rect onclick="bad()" width="10"/><use href="https://example.com/x.svg"/></svg>'
    clean=safe_svg(svg).decode()
    assert '<script' not in clean and 'foreignObject' not in clean and 'onclick' not in clean and 'https://' not in clean

def test_svg_rejects_entities():
    with pytest.raises(ValueError):safe_svg(b'<!DOCTYPE svg [<!ENTITY secret SYSTEM "file:///etc/passwd">]><svg>&secret;</svg>')

def test_numeric_react_attributes():
    assert 'tabIndex={0}' in jsx_attrs({'tabindex':'0'})
    assert 'maxLength={12}' in jsx_attrs({'maxlength':'12'})
    assert 'playsInline={true}' in jsx_attrs({'playsinline':''})

def test_collector_svg_localisation_and_css(tmp_path):
    source=tmp_path/'source';source.mkdir()
    (source/'r.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10" fill="red"/></svg>')
    with local_site(source) as origin:
        collector=AssetCollector(SafeFetcher(test_origin=origin),tmp_path/'assets')
        css=collector.stylesheet('.hero{background-image:url("r.svg")} @media(max-width:500px){.hero{display:block}}',origin+'/site.css')
        assert 'url("assets/' in css and '@media' in css
        assert len(collector.manifest)==1
        assert len(list((tmp_path/'assets').glob('*.svg')))==1

def test_script_handlers_and_text_escaping(tmp_path):
    from collections import Counter
    collector=AssetCollector(SafeFetcher(),tmp_path/'assets');texts={}
    raw={'id':'a','tag':'div','attrs':{'onclick':'alert(1)','style':'color:red','id':'safe'},'children':[{'id':'t','text':'<script>alert("x")</script>'}]}
    node=clean_tree(raw,'p0',collector,'https://example.com',texts,Counter())
    assert 'onclick' not in node['attrs']
    out=to_html(node,{'route':'/'},{'texts':texts,'pages':[]})
    assert '&lt;script&gt;' in out and '<script>' not in out

def test_local_route_alias():
    ir={'pages':[{'url':'https://example.com/','route':'/'},{'url':'https://example.com/about/','route':'/about/'}]}
    node={'tag':'a','attrs':{'href':'https://example.com/index.html#work'}}
    assert attrs_for(node,{'route':'/about/'},ir,False)['href']=='../index.html#work'

def test_redirect_destination_revalidated():
    f=SafeFetcher()
    f.cache['https://example.com/']=Response('https://example.com/',302,{'location':'http://127.0.0.1/'},b'')
    with pytest.raises(NetworkError):f.get('https://example.com/',follow=True)

def test_queue_bound(client):
    statuses=[client.post('/api/jobs',headers=AUTH,json={'demo':True,'permission':True}).status_code for _ in range(13)]
    assert statuses.count(202)==12 and statuses[-1]==429
