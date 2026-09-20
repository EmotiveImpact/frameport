"""Pinned-IP fetching: the browser never chooses the DNS answer for HTTP traffic.

Only GET/HEAD, globally routable addresses, standard ports, bounded responses.
The sole private exception is a server-created demo origin, never user input.
Production must additionally use sandboxed workers and network-level egress rules.
"""
from __future__ import annotations
from dataclasses import dataclass
import gzip
import http.client
import ipaddress
import socket
import ssl
import threading
from urllib.parse import urlsplit, urlunsplit, urljoin

class NetworkError(ValueError):
    pass

def normalise_url(raw: str) -> str:
    raw = raw.strip()
    if not raw or any(ord(c) < 32 for c in raw) or "\\" in raw:
        raise NetworkError("Enter a valid public http:// or https:// website address.")
    if "://" not in raw:
        raw = "https://" + raw
    try:
        u = urlsplit(raw)
        if u.scheme not in ("http", "https") or not u.hostname or u.username is not None or u.password is not None:
            raise NetworkError("Only public HTTP(S) addresses without credentials are allowed.")
        host = u.hostname.encode("idna").decode().lower().rstrip(".")
        port = u.port
        if port is not None and port not in (80, 443):
            raise NetworkError("Public conversions only support ports 80 and 443.")
        host = f"[{host}]" if ":" in host else host
        netloc = host + (f":{port}" if port else "")
        return urlunsplit((u.scheme, netloc, u.path or "/", u.query, ""))
    except (UnicodeError, ValueError) as e:
        if isinstance(e, NetworkError):
            raise
        raise NetworkError("That website address could not be parsed.") from e

def public_ip(raw: str) -> bool:
    try:
        ip = ipaddress.ip_address(raw)
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        return ip.is_global and not (ip.is_multicast or ip.is_reserved or ip.is_unspecified or ip.is_loopback or ip.is_link_local)
    except ValueError:
        return False

@dataclass
class Response:
    url: str
    status: int
    headers: dict[str, str]
    body: bytes

class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname: str, ip: str, port: int, timeout: float):
        super().__init__(hostname, port, timeout=timeout, context=ssl.create_default_context())
        self.pinned_ip = ip

    def connect(self):
        sock = socket.create_connection((self.pinned_ip, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise

class SafeFetcher:
    def __init__(self, test_origin: str | None = None, max_bytes=120_000_000, max_requests=1200):
        self.test_origin = test_origin.rstrip("/") if test_origin else None
        self.max_bytes = max_bytes
        self.max_requests = max_requests
        self.used_bytes = 0
        self.requests = 0
        self.blocked: set[str] = set()
        self.cache: dict[str, Response] = {}
        self.lock = threading.Lock()
        self.gate = threading.BoundedSemaphore(10)
        self.closed = False

    def target(self, raw: str):
        u = urlsplit(raw)
        origin = f"{u.scheme}://{u.netloc}"
        if self.test_origin and origin == self.test_origin:
            if u.hostname != "127.0.0.1" or u.username or u.password:
                raise NetworkError("Invalid internal demo origin.")
            return u, "127.0.0.1"
        clean = normalise_url(raw)
        u = urlsplit(clean)
        host = u.hostname or ""
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".home", ".lan")) or "%" in host:
            raise NetworkError("Private and local network addresses are not allowed.")
        try:
            answers = socket.getaddrinfo(host, u.port or (443 if u.scheme == "https" else 80), type=socket.SOCK_STREAM)
        except OSError as e:
            raise NetworkError(f"Cannot resolve {host}. Check the address and worker network access.") from e
        ips = {answer[4][0] for answer in answers}
        if not ips or not all(public_ip(ip) for ip in ips):
            raise NetworkError("The hostname resolves to a private or reserved network address.")
        return u, sorted(ips, key=lambda ip: (":" in ip, ip))[0]

    def get(self, raw: str, follow=False, depth=0) -> Response:
        if self.closed:
            raise NetworkError("Conversion cancelled.")
        with self.lock:
            if raw in self.cache:
                result = self.cache[raw]
            else:
                result = None
        if result is None:
            result = self._request(raw)
        if follow and result.status in (301, 302, 303, 307, 308):
            if depth >= 5:
                raise NetworkError("Too many redirects.")
            location = result.headers.get("location")
            if not location:
                raise NetworkError("Redirect is missing its destination.")
            return self.get(urljoin(raw, location), follow=True, depth=depth + 1)
        return result

    def _request(self, raw: str) -> Response:
        with self.gate:
            with self.lock:
                self.requests += 1
                if self.requests > self.max_requests or self.used_bytes > self.max_bytes:
                    raise NetworkError("This site exceeds the bounded conversion resource budget.")
            try:
                u, ip = self.target(raw)
                port = u.port or (443 if u.scheme == "https" else 80)
                conn = PinnedHTTPS(u.hostname or "", ip, port, 12) if u.scheme == "https" else http.client.HTTPConnection(ip, port, timeout=12)
                try:
                    path = urlunsplit(("", "", u.path or "/", u.query, ""))
                    conn.request("GET", path, headers={"Host": u.netloc, "User-Agent": "Frameport/0.1 (authorised site export)", "Accept": "*/*", "Accept-Encoding": "identity"})
                    response = conn.getresponse()
                    body = response.read(12_000_001)
                    if len(body) > 12_000_000:
                        raise NetworkError("A resource exceeds the 12 MB limit.")
                    headers = {k.lower(): v for k, v in response.getheaders()}
                    if headers.get("content-encoding") == "gzip":
                        import io
                        with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
                            body = stream.read(12_000_001)
                        if len(body) > 12_000_000:
                            raise NetworkError("A decompressed resource exceeds the 12 MB limit.")
                        headers.pop("content-encoding", None)
                    elif headers.get("content-encoding") not in (None, "identity"):
                        raise NetworkError("The server ignored identity encoding; resource was not imported.")
                    for h in ("transfer-encoding", "content-length", "connection", "set-cookie", "alt-svc", "clear-site-data", "strict-transport-security"):
                        headers.pop(h, None)
                    result = Response(raw, response.status, headers, body)
                finally:
                    conn.close()
                with self.lock:
                    self.used_bytes += len(body)
                    if self.used_bytes > self.max_bytes:
                        raise NetworkError("Conversion download budget exceeded.")
                    self.cache[raw] = result
                return result
            except (OSError, http.client.HTTPException, ValueError) as e:
                self.blocked.add(raw[:300])
                if isinstance(e, NetworkError):
                    raise
                raise NetworkError(f"Could not safely fetch {urlsplit(raw).hostname}: {type(e).__name__}") from e
