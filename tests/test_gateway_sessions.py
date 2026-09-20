"""The gateway pool must never share credentials across independent visitors."""
import httpx
from fastapi.testclient import TestClient
from frameport.gateway import create_gateway


def test_gateway_does_not_share_upstream_cookie_jar_between_visitors():
    """A pooled HTTP client must never become a shared signed-in browser."""
    seen=[]
    def upstream(request):
        seen.append(request)
        if request.url.path=='/api/session' and request.method=='POST':
            return httpx.Response(200,json={'authenticated':True},headers={'set-cookie':'frameport_session=owner-secret; HttpOnly; Path=/; SameSite=strict'})
        if request.url.path=='/api/health':
            return httpx.Response(200,json={'worker':'available','canConvert':True})
        return httpx.Response(200 if request.headers.get('cookie')=='frameport_session=owner-secret' else 401,json={'ok':True})
    gateway=create_gateway('https://worker.example',transport=httpx.MockTransport(upstream))
    owner=TestClient(gateway)
    visitor=TestClient(gateway)
    assert owner.post('/api/session',json={'key':'owner-key'}).status_code==200
    assert owner.get('/api/jobs').status_code==200
    assert visitor.get('/api/jobs').status_code==401
    assert not seen[-1].headers.get('cookie')
    visitor.get('/api/health')
    assert not seen[-1].headers.get('cookie')
