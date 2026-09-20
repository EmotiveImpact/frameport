"""Restricted-environment test adapter. NEVER used by the production application.

Chromium navigation is blocked by this execution environment's administrator.
This adapter leaves that policy intact. It renders only files in our original
fixture or the generated output using set_content. It does NOT access blocked
websites, proxy browser navigation, or claim to test actual HTTP navigation.

Real DNS-pinned HTTP asset fetching is tested separately by the normal pipeline.
"""
from __future__ import annotations
import base64
import mimetypes
import re
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit, urljoin, unquote
from unittest.mock import patch
from contextlib import contextmanager
from bs4 import BeautifulSoup
from playwright.async_api import Page
from frameport.config import ROOT
from frameport.engine.capture import EXTRACT


def inline_document(folder: Path, relative: str, origin: str, document_url: str | None = None):
    """Inline known local resources. External resources are rejected, not fetched."""
    folder = folder.resolve()
    document = (folder / relative).resolve()
    if not document.is_relative_to(folder) or not document.is_file():
        raise ValueError("Offline harness can only render existing local fixture files")
    soup = BeautifulSoup(document.read_text(), "html.parser")
    full_url = document_url or urljoin(origin+"/", relative)
    base = soup.new_tag('base',href=full_url)
    if soup.head: soup.head.insert(0,base)
    styles = []
    def local(resource, at):
        url = urljoin(at,resource)
        if urlsplit(url).netloc != urlsplit(origin).netloc:
            raise ValueError("External resource rejected by offline harness: "+url)
        f = (folder/unquote(urlsplit(url).path).lstrip('/')).resolve()
        if not f.is_relative_to(folder) or not f.is_file():
            raise ValueError("Missing local resource in offline harness: "+str(f))
        return f,url
    def data(f):
        return 'data:'+(mimetypes.guess_type(f.name)[0] or 'application/octet-stream')+';base64,'+base64.b64encode(f.read_bytes()).decode()
    def inline_css(css,at):
        def replace(m):
            raw=m[1].strip(" \"'")
            if raw.startswith(('data:','#')):return m[0]
            f,_=local(raw,at)
            return 'url("'+data(f)+'")'
        return re.sub(r'url\(([^)]+)\)',replace,css)
    for tag in list(soup.find_all('link',rel='stylesheet')):
        f,url=local(tag.get('href',''),full_url)
        original=f.read_text();styles.append(dict(css=original,base=url))
        replacement=soup.new_tag('style');replacement.string=inline_css(original,url);tag.replace_with(replacement)
    for tag in list(soup.find_all('script',src=True)):
        f,_=local(tag['src'],full_url)
        del tag['src'];tag.string=f.read_text()
    for tag in soup.find_all(['img','video','audio']):
        if tag.get('src') and not tag['src'].startswith('data:'):
            f,url=local(tag['src'],full_url)
            tag['data-frameport-test-original-src']=url
            tag['src']=data(f)
    return str(soup),styles,full_url

@contextmanager
def offline_rendering(job_root: Path):
    original_evaluate = Page.evaluate
    async def local_goto(page, url, **kwargs):
        # No actual network navigation occurs. Only the original fixture and
        # this test's output directory are eligible document sources.
        u=urlsplit(url)
        if u.hostname!='127.0.0.1':
            raise ValueError('Offline renderer refuses non-fixture URLs')
        folder=job_root/'html' if (job_root/'html').is_dir() else ROOT/'fixtures'/'forma'
        relative=u.path.lstrip('/') or 'index.html'
        if relative.endswith('/'):relative+='index.html'
        html,styles,full=inline_document(folder,relative,f'{u.scheme}://{u.netloc}',url)
        page._fp_test_source=(url,styles)
        await page.set_content(html,wait_until='load')
        return SimpleNamespace(status=200)
    async def evaluate(page, expression, arg=None):
        result=await original_evaluate(page,expression,arg)
        if expression==EXTRACT:
            full,styles=page._fp_test_source
            result['url']=full
            result['styles']=styles
            def restore(node):
                attrs=node.get('attrs',{})
                original=attrs.pop('data-frameport-test-original-src',None)
                if original:attrs['src']=original
                for child in node.get('children',[]):restore(child)
            restore(result['tree'])
        return result
    with patch.object(Page,'goto',local_goto),patch.object(Page,'evaluate',evaluate):
        yield
