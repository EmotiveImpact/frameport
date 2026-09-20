from __future__ import annotations
import asyncio
import json
import shutil
import time
import zipfile
from pathlib import Path
from .network import SafeFetcher, normalise_url
from .capture import capture_site
from .assets import AssetCollector
from .compiler import prepare_ir, generate, write
from .validate import local_site, validate
from ..config import ROOT

async def convert_job(record, store, settings):
    ident = record["id"]
    root = settings.data/"jobs"/ident
    root.mkdir(parents=True,exist_ok=True)
    def progress(stage,amount,message): store.event(ident,stage,amount,message)
    def cancelled():
        current = store.get(ident)
        return not current or current.get("cancelled",False)
    options = record["request"]
    progress("Inspect",4,"Checking permission, URL and conversion limits")
    if not options["permission"]:
        raise ValueError("Confirm that you own this website or have permission to export it.")
    fetcher = None
    try:
        store.update(ident,status="running")
        async with asyncio.timeout(settings.max_job_seconds):
            if record.get("pendingPatches"):
                ir = json.loads((root/"model.json").read_text())
                for patch in record["pendingPatches"]:
                    if patch["id"] not in ir["texts"]:
                        raise ValueError("A text field no longer exists. Reload the editor.")
                    ir["texts"][patch["id"]] = patch["text"]
                progress("Generate",60,"Rebuilding the edited content and invalidating old visual evidence")
            else:
                if options["demo"]:
                    # The user cannot supply or change this private-network exception.
                    with local_site(ROOT/"fixtures"/"forma") as fixture_origin:
                        fetcher = SafeFetcher(test_origin=fixture_origin)
                        captured = await capture_site(fixture_origin+"/",options,settings,root,fetcher,progress,cancelled)
                        progress("Extract",48,"Collecting stylesheets and resolving local asset copies")
                        collector = AssetCollector(fetcher,root/"assets")
                        ir = await asyncio.to_thread(prepare_ir,captured,collector)
                else:
                    target = normalise_url(options["url"])
                    fetcher = SafeFetcher()
                    await asyncio.to_thread(fetcher.target,target)
                    captured = await capture_site(target,options,settings,root,fetcher,progress,cancelled)
                    progress("Extract",48,"Collecting stylesheets and resolving local asset copies")
                    collector = AssetCollector(fetcher,root/"assets")
                    ir = await asyncio.to_thread(prepare_ir,captured,collector)
                if fetcher.blocked:
                    ir["issues"].append(dict(code="capture-network",severity="warning",message=f"{len(fetcher.blocked)} source resources could not be fetched safely. Capture may be incomplete."))
            if options.get("bridge") and not record.get("pendingPatches"):
                ir["bridge"] = options["bridge"]
                ir["issues"].append(dict(code="project-bridge",severity="info",message="Project metadata and CMS records are included as reference JSON. This release does not compile the Framer canvas or automatically bind CMS data to routes."))
            if cancelled(): raise asyncio.CancelledError()
            progress("Generate",60,"Writing semantic HTML, React components and editable content files")
            generated = await asyncio.to_thread(generate,ir,root)
            write(root/"model.json",json.dumps(ir,ensure_ascii=False))
            report = await validate(ir,root,settings,progress,cancelled)
            report.update(components=generated["components"],assets=len(ir["assets"]),nodes=ir["nodes"],textCount=generated["textCount"],pages=[dict(key=p["key"],route=p["route"],title=p["title"],framerDetected=p["framer"]) for p in ir["pages"]],revision=record.get("revision",0),demo=options["demo"],createdAt=time.time())
            if record.get("revision",0):
                report["issues"].append(dict(code="edited-content",severity="info",message="This export includes your content edits. Visual comparisons still use the original site, so intentional changes may appear as differences.",count=1))
            progress("Package",95,"Packaging the projects and their actual verification report")
            write(root/"report.json",json.dumps(report,indent=2))
            for target in ("html","react"):
                if ir.get("bridge"):
                    write(root/target/"project-manifest.json",json.dumps(ir["bridge"],indent=2,ensure_ascii=False))
                    write(root/target/"cms-content.json",json.dumps(ir["bridge"].get("collections",[]),indent=2,ensure_ascii=False))
                write(root/target/"conversion-report.json",json.dumps(report,indent=2))
                write(root/target/"asset-manifest.json",json.dumps(ir["assets"],indent=2))
                temp = root/f"{target}.zip.part"
                with zipfile.ZipFile(temp,"w",zipfile.ZIP_DEFLATED) as z:
                    for path in sorted((root/target).rglob("*")):
                        if path.is_file(): z.write(path,path.relative_to(root/target))
                temp.replace(root/f"{target}.zip")
            write(root/"COMPLETE",str(time.time()))
            store.update(ident,status="completed",stage="Complete",progress=100,report=report,error=None,pendingPatches=None)
            progress("Complete",100,"Export ready. Review the report before publishing.")
    finally:
        if fetcher: fetcher.closed = True

async def run_guarded(record,store,settings):
    ident = record["id"]
    root = settings.data/"jobs"/ident
    for path in (root/"COMPLETE",root/"html.zip",root/"react.zip"):
        path.unlink(missing_ok=True)
    try:
        await convert_job(record,store,settings)
    except asyncio.CancelledError:
        store.update(ident,status="cancelled",stage="Cancelled",error="Conversion cancelled. No completed export is available.")
    except TimeoutError:
        store.update(ident,status="failed",stage="Stopped",error=f"The conversion exceeded the {settings.max_job_seconds}-second job limit. Try one page or a smaller site.")
    except Exception as error:
        store.update(ident,status="failed",stage="Failed",error=str(error)[:600])
    finally:
        current = store.get(ident)
        if current and current["status"] != "completed":
            for p in (root/"COMPLETE",root/"html.zip",root/"react.zip"):
                p.unlink(missing_ok=True)
