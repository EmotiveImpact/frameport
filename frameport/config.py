from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent

@dataclass(frozen=True)
class Settings:
    data: Path = field(default_factory=lambda: Path(os.environ.get("FRAMEPORT_DATA", ".frameport")).resolve())
    api_key: str = field(default_factory=lambda: os.environ.get("FRAMEPORT_API_KEY", ""))
    allowed_hosts: tuple[str, ...] = field(default_factory=lambda: tuple(os.environ.get("FRAMEPORT_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")))
    chromium_path: str | None = field(default_factory=lambda: os.environ.get("FRAMEPORT_CHROMIUM_PATH") or None)
    unsandboxed_test_browser: bool = field(default_factory=lambda: os.environ.get("FRAMEPORT_UNSANDBOXED_TEST_BROWSER") == "1")
    retention_days: int = field(default_factory=lambda: max(1, min(30, int(os.environ.get("FRAMEPORT_RETENTION_DAYS", "7")))))
    max_job_seconds: int = 240
    workers: int = 1
    max_pending: int = 12
    max_storage_bytes: int = 2_000_000_000
