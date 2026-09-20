from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import os

def env_int(name: str, default: int, low: int, high: int) -> int:
    raw = os.environ.get(name, '').strip()
    try:
        return max(low, min(high, int(raw))) if raw else default
    except ValueError:
        return default

def allowed_hosts() -> tuple[str, ...]:
    configured = os.environ.get('FRAMEPORT_ALLOWED_HOSTS', '').strip()
    if configured:
        return tuple(x.strip() for x in configured.split(',') if x.strip())
    hosts = ['localhost', '127.0.0.1', '[::1]', 'healthcheck.railway.app']
    railway = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '').strip()
    if railway:
        hosts.append(railway)
    return tuple(hosts)

ROOT = Path(__file__).resolve().parent.parent

@dataclass(frozen=True)
class Settings:
    data: Path = field(default_factory=lambda: Path(os.environ.get("FRAMEPORT_DATA") or ".frameport").resolve())
    api_key: str = field(default_factory=lambda: os.environ.get("FRAMEPORT_API_KEY", ""))
    allowed_hosts: tuple[str, ...] = field(default_factory=allowed_hosts)
    chromium_path: str | None = field(default_factory=lambda: os.environ.get("FRAMEPORT_CHROMIUM_PATH") or None)
    unsandboxed_test_browser: bool = field(default_factory=lambda: os.environ.get("FRAMEPORT_UNSANDBOXED_TEST_BROWSER") == "1")
    retention_days: int = field(default_factory=lambda: env_int("FRAMEPORT_RETENTION_DAYS", 7, 1, 30))
    max_job_seconds: int = 240
    workers: int = 1
    max_pending: int = 12
    max_storage_bytes: int = 2_000_000_000
    public_origin: str = field(default_factory=lambda: os.environ.get("FRAMEPORT_PUBLIC_ORIGIN", "").rstrip("/"))
    managed_storage: bool = field(default_factory=lambda: bool(os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")))
    session_days: int = 7
