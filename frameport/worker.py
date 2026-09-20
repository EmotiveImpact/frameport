"""Durable-queue supervisor and isolated per-conversion subprocess entrypoint.

Only the persistent service starts this supervisor. Vercel never imports it.
Job inputs are data, never shell commands. Cancellation and timeouts terminate
its process group so a runaway browser cannot silently outlive the job.
"""
from __future__ import annotations
import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import signal
import sys
import time
from .config import Settings
from .store import Store


def worker_environment(settings):
    # Do not pass API keys, session credentials or unrelated cloud credentials to
    # the browser execution process. Chromium's sandbox remains required.
    env = {k: v for k, v in os.environ.items() if k in {
        'PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR', 'TMP', 'TEMP', 'PYTHONPATH',
        'VIRTUAL_ENV', 'PLAYWRIGHT_BROWSERS_PATH', 'LD_LIBRARY_PATH', 'SYSTEMROOT'}}
    env['PYTHONUNBUFFERED'] = '1'
    env['FRAMEPORT_JOB_CONFIG'] = json.dumps({
        'data': str(settings.data), 'chromium_path': settings.chromium_path,
        'unsandboxed_test_browser': settings.unsandboxed_test_browser,
        'max_job_seconds': settings.max_job_seconds,
    })
    return env


class Supervisor:
    def __init__(self, store, settings):
        self.store, self.settings = store, settings
        self.ready, self.message, self.active = False, 'Checking browser worker.', None
        self.lock = None
        self.task = None

    async def start(self):
        if not self.settings.workers:
            self.message = 'Worker execution is disabled.'
            return
        self.lock = open(self.settings.data / 'worker.lock', 'a+b')
        try:
            if os.name == 'posix':
                import fcntl
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                import msvcrt
                self.lock.write(b'0'); self.lock.flush(); self.lock.seek(0)
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self.lock.close(); self.lock = None
            self.message = 'Another supervisor owns this data volume. Use one service replica.'
            return
        try:
            from playwright.async_api import async_playwright
            from .engine.capture import launch_browser
            async with async_playwright() as pw:
                browser = await launch_browser(pw, self.settings)
                await browser.close()
        except Exception:
            self.message = 'Chromium could not start safely. Check installation and sandbox support.'
            self.lock.close(); self.lock = None
            return
        for record in self.store.list(10000):
            if record['status'] == 'running':
                self.store.interrupt(record['id'])
        self.ready, self.message = True, 'Browser worker connected.'
        self.task = asyncio.create_task(self.loop())

    async def stop_process(self, proc):
        if proc.returncode is not None:
            return
        try:
            if os.name == 'posix':
                os.killpg(proc.pid, signal.SIGTERM)
            else:
                proc.terminate()
            await asyncio.wait_for(proc.wait(), 3)
        except asyncio.TimeoutError:
            if os.name == 'posix':
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
            await proc.wait()
        except ProcessLookupError:
            pass

    async def loop(self):
        try:
            while True:
                record = self.store.claim_next()
                if not record:
                    await asyncio.sleep(.35)
                    continue
                ident = record['id']
                proc = None
                try:
                    proc = await asyncio.create_subprocess_exec(
                        sys.executable, '-m', 'frameport.worker', '--job', ident,
                        cwd=str(Path(__file__).resolve().parent.parent), env=worker_environment(self.settings),
                        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                        start_new_session=os.name == 'posix')
                    self.active = proc
                    deadline = time.monotonic()+self.settings.max_job_seconds+10
                    while proc.returncode is None:
                        latest = self.store.get(ident)
                        if latest and latest.get('cancelled'):
                            await self.stop_process(proc)
                            self.store.update(ident, status='cancelled', stage='Cancelled', error='Conversion cancelled. No completed export is available.')
                            break
                        if time.monotonic() > deadline:
                            await self.stop_process(proc)
                            self.store.update(ident, status='failed', stage='Stopped', error='Conversion exceeded the worker time limit.')
                            break
                        try:
                            await asyncio.wait_for(proc.wait(), .35)
                        except asyncio.TimeoutError:
                            pass
                    latest = self.store.get(ident)
                    if latest and latest['status'] == 'running':
                        self.store.update(ident, status='failed', stage='Failed', error='The browser execution process exited before completing its export.')
                    self.store.record_revision(ident)
                except asyncio.CancelledError:
                    if proc:
                        await self.stop_process(proc)
                    self.store.interrupt(ident)
                    raise
                except Exception:
                    if proc:
                        await self.stop_process(proc)
                    self.store.update(ident, status='failed', stage='Failed', error='Could not run this conversion. Check worker configuration.')
                finally:
                    self.active = None
        finally:
            self.ready = False

    async def close(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        if self.lock:
            self.lock.close(); self.lock = None
        self.ready = False


def main():
    import argparse, re
    parser = argparse.ArgumentParser(); parser.add_argument('--job', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{32}', args.job):
        raise SystemExit('Invalid job identifier')
    values = json.loads(os.environ['FRAMEPORT_JOB_CONFIG'])
    values['data'] = Path(values['data'])
    settings = Settings(**values, api_key='')
    store = Store(settings.data)
    record = store.get(args.job)
    if not record or record['status'] != 'running' or record.get('cancelled'):
        raise SystemExit('Job is no longer eligible for execution')
    from .engine.pipeline import run_guarded
    asyncio.run(run_guarded(record, store, settings))

if __name__ == '__main__':
    main()
