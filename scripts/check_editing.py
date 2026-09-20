"""API and real regeneration check against an existing, measured fixture export."""
import argparse,asyncio,json,shutil
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from frameport.app import create_app
from frameport.config import Settings
from frameport.engine.pipeline import run_guarded
from frameport.engine.validate import validate as original_validate
from tests.offline_browser import offline_rendering

async def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--data',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    original=json.loads(Path(a.job).read_text()); source=Path(a.data)/'jobs'/original['id']
    settings=Settings(data=Path(a.data).resolve(),allowed_hosts=('testserver',))
    app=create_app(settings);store=app.state.store
    job=store.create(original['request']);root=settings.data/'jobs'/job['id'];shutil.copytree(source,root)
    store.update(job['id'],status='completed',progress=100,stage='Complete',report=original['report'])
    client=TestClient(app);base='/api/jobs/'+job['id'];checks=[]
    def check(name,condition):
        assert condition,name;checks.append({'name':name,'passed':True})
    record=client.get(base).json();ticket=record['ticket']
    check('Completed React ZIP downloadable',client.get(base+'/download/react').status_code==200)
    check('Scoped preview serves HTML',client.get(f"/preview/{job['id']}/{ticket}/index.html").status_code==200)
    check('Forged ticket rejected',client.get(f"/preview/{job['id']}/0-nope/index.html").status_code==403)
    content=client.get(base+'/content').json()
    field=next(x for x in content if 'A little different.' in x['text'])
    text='A completely new direction. <script>window.compromised=true</script>'
    response=client.post(base+'/edits',json={'patches':[{'id':field['id'],'text':text}]})
    check('Edit accepted and revision incremented',response.status_code==202 and response.json()['revision']==1)
    check('Old exports blocked during rebuild',client.get(base+'/download/react').status_code==409)
    check('Old preview invalidated',client.get(f"/preview/{job['id']}/{ticket}/index.html").status_code==409)
    async def measured(*args,**kwargs):
        report=await original_validate(*args,**kwargs)
        report['execution']={'mode':'offline-document-harness','browserNavigationVerified':False,'description':'Authored local files rendered using set_content. This edit/regeneration test does not verify browser HTTP navigation or a live Framer site.'}
        return report
    with offline_rendering(root),patch('frameport.engine.pipeline.validate',measured):
        await run_guarded(store.get(job['id']),store,settings)
    updated=store.get(job['id']);check('Regeneration completed',updated['status']=='completed')
    check('New React JSON contains edit',json.loads((root/'react/src/content/site.json').read_text())[field['id']]==text)
    html=(root/'html/index.html').read_text()
    check('HTML edit escaped rather than executed','&lt;script&gt;window.compromised=true&lt;/script&gt;' in html)
    check('Intentional visual difference detected',not updated['report']['visualPassed'])
    check('Rebuilt ZIP downloadable',client.get(base+'/download/react').status_code==200)
    check('Revision invalidates old signed ticket',client.get(f"/preview/{job['id']}/{ticket}/index.html").status_code==403)
    fresh=client.get(base).json();check('New ticket works',client.get(f"/preview/{job['id']}/{fresh['ticket']}/index.html").status_code==200)
    check('Unknown content field rejected',client.post(base+'/edits',json={'patches':[{'id':'not-a-field','text':'x'}]}).status_code==422)
    result={'job':job['id'],'mode':'actual API requests and export regeneration; offline-document Chromium harness','checks':checks,'changedComparisons':sum(not c['passed'] for c in updated['report']['comparisons'])}
    Path(a.output).write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':asyncio.run(main())
