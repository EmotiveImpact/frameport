"""Package actual fixture output as a self-contained, read-only studio preview."""
import argparse,base64,json,mimetypes,re
from pathlib import Path
from frameport.config import ROOT

def data(path):
    mime=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    return 'data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode()

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--data',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    job=json.loads(Path(a.job).read_text());assert job['status']=='completed'
    root=Path(a.data)/'jobs'/job['id']
    assert (root/'COMPLETE').exists()
    readable={'.ts','.tsx','.js','.json','.css','.html','.md','.svg'}
    payload=dict(job=job,evidence={f.name:data(f) for f in (root/'evidence').glob('*.png')},files={str(f.relative_to(root/'react')):f.read_text() for f in (root/'react').rglob('*') if f.is_file() and f.suffix in readable},htmlFiles={str(f.relative_to(root/'html')):f.read_text() for f in (root/'html').rglob('*') if f.is_file() and f.suffix in readable},content=[dict(id=k,text=v) for k,v in json.loads((root/'model.json').read_text())['texts'].items() if v.strip()],downloads={t:data(root/f'{t}.zip') for t in ('react','html')})
    document=(ROOT/'web/index.html').read_text()
    document=re.sub(r'<link[^>]+rel="icon"[^>]*>','',document)
    document=document.replace('<link rel="stylesheet" href="/static/style.css">','<style>'+(ROOT/'web/style.css').read_text()+'</style>')
    setup='<script>window.__FRAMEPORT_PREVIEW__='+json.dumps(payload,ensure_ascii=True).replace('</','<\\/')+';</script>'
    code=(ROOT/'web/dist/app.js').read_text().replace('</script','<\\/script')
    # The portable preview resolves our sole local shader module without a server.
    shader=base64.b64encode((ROOT/'web/dist/eclipse.js').read_bytes()).decode()
    code=code.replace("from './eclipse.js'", "from 'data:text/javascript;base64,"+shader+"'")
    document=document.replace('<script type="module" src="/static/dist/app.js"></script>',setup+'<script type="module">'+code+'</script>')
    Path(a.output).write_text(document)
    print(a.output,Path(a.output).stat().st_size)
if __name__=='__main__':main()
