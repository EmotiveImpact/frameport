from __future__ import annotations
import argparse
import os
import uvicorn
from .app import create_app
from .config import Settings, env_int

def main():
    parser = argparse.ArgumentParser(description="Frameport conversion studio")
    parser.add_argument("--host",default=(os.environ.get("FRAMEPORT_HOST") or "127.0.0.1"))
    parser.add_argument("--port",type=int,default=env_int("FRAMEPORT_PORT",8040,1,65535))
    args = parser.parse_args()
    settings = Settings()
    if args.host not in ("127.0.0.1","localhost","::1") and len(settings.api_key)<24:
        parser.error("Binding beyond loopback requires FRAMEPORT_API_KEY with at least 24 characters. This is a single-workspace developer release, not an unaudited public SaaS.")
    if settings.unsandboxed_test_browser:
        print("WARNING: Chromium sandbox is disabled for trusted local tests only. Do not expose this worker or capture untrusted sites.")
    uvicorn.run(create_app(settings),host=args.host,port=args.port,log_level="info")

if __name__ == "__main__": main()
