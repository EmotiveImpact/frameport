"""Run the real pipeline on the original fixture; optionally use offline rendering."""
import argparse
import asyncio
import json
from pathlib import Path
from unittest.mock import patch
from frameport.config import Settings
from frameport.models import ConvertRequest
from frameport.store import Store
from frameport.engine.pipeline import run_guarded
from frameport.engine.validate import validate as production_validate

async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--offline',action='store_true',help='Use authored-file rendering instead of browser HTTP navigation; report this substitution.')
    parser.add_argument('--data',default='.frameport-check')
    parser.add_argument('--output',default='fixture-result.json')
    args=parser.parse_args()
    settings=Settings(data=Path(args.data).resolve())
    store=Store(settings.data)
    record=store.create(ConvertRequest(demo=True,permission=True,name='Forma Studio',max_pages=3).model_dump(by_alias=True))
    root=settings.data/'jobs'/record['id']
    print('JOB',record['id'],flush=True)
    if args.offline:
        from tests.offline_browser import offline_rendering
        async def measured(*a,**kw):
            report=await production_validate(*a,**kw)
            report['execution']={'mode':'offline-document-harness','browserNavigationVerified':False,'description':'Only original local fixture files and generated files were rendered with set_content. Administrator browser navigation restrictions were not changed. This is not a live Framer benchmark.'}
            return report
        with offline_rendering(root),patch('frameport.engine.pipeline.validate',measured):
            await run_guarded(record,store,settings)
    else:
        await run_guarded(record,store,settings)
    job=store.get(record['id'])
    Path(args.output).write_text(json.dumps(job,indent=2))
    report=job.get('report') or {}
    print(json.dumps(dict(id=job['id'],status=job['status'],error=job.get('error'),verdict=report.get('verdict'),comparisons=[dict(page=c['page'],width=c['width'],passed=c['passed'],difference=c.get('differencePercent')) for c in report.get('comparisons',[])],checks=report.get('checks'),issues=report.get('issues')),indent=2),flush=True)
    if job['status']!='completed' or report.get('verdict')!='visual-pass':raise SystemExit(1)

if __name__=='__main__':asyncio.run(main())
