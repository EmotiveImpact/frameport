from __future__ import annotations
import base64
import hashlib
import mimetypes
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import tinycss2
from .network import SafeFetcher, NetworkError

ASSET_MARK = "/__FRAMEPORT_ASSET__/"
ALLOWED_MIME = {
    "image/png":".png", "image/jpeg":".jpg", "image/webp":".webp", "image/gif":".gif", "image/avif":".avif", "image/svg+xml":".svg", "image/x-icon":".ico",
    "font/woff":".woff", "font/woff2":".woff2", "font/ttf":".ttf", "font/otf":".otf", "application/font-woff":".woff", "application/x-font-ttf":".ttf",
    "video/mp4":".mp4", "video/webm":".webm", "audio/mpeg":".mp3", "audio/ogg":".ogg"
}

def safe_svg(raw: bytes) -> bytes:
    import xml.etree.ElementTree as ET
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("SVG entities are not supported")
    root = ET.fromstring(raw)
    forbidden = {"script","foreignobject","iframe","object","embed","animate","animatetransform","animatemotion","set","style"}
    for parent in list(root.iter()):
        for child in list(parent):
            if child.tag.split('}')[-1].lower() in forbidden:
                parent.remove(child)
        for key, value in list(parent.attrib.items()):
            k = key.split('}')[-1].lower()
            if k.startswith("on") or (k in ("href", "src") and not value.startswith("#")) or ("url(" in value.lower() and not re.fullmatch(r"url\(\s*['\"]?#[\w.-]+['\"]?\s*\)", value)):
                del parent.attrib[key]
    return ET.tostring(root, encoding="utf-8")

class AssetCollector:
    def __init__(self, fetcher: SafeFetcher, directory: Path):
        self.fetcher = fetcher
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.urls: dict[str, str] = {}
        self.manifest: list[dict] = []
        self.issues: list[dict] = []
        self.css_seen: set[str] = set()

    def issue(self, code, message):
        self.issues.append(dict(code=code, severity="warning", message=message))

    def asset(self, raw: str, base: str, css=False) -> str:
        if not raw or raw.startswith("#"):
            return raw
        if raw.startswith(ASSET_MARK):
            return raw.removeprefix(ASSET_MARK) if css else raw
        if raw.startswith("data:"):
            if len(raw) < 3_000_000 and re.match(r"^data:image/(png|jpeg|gif|webp|avif);base64,", raw, re.I):
                return raw
            self.issue("inline-resource", "An unsupported inline resource was removed; only bounded raster data images are retained.")
            return "data:,"
        absolute = urljoin(base, raw)
        if absolute in self.urls:
            value = self.urls[absolute]
            return value.removeprefix("/") if css else value.replace("assets/", ASSET_MARK, 1)
        try:
            if len(self.manifest) >= 300:
                raise NetworkError("More than 300 assets")
            r = self.fetcher.get(absolute, follow=True)
            if r.status != 200:
                raise NetworkError(f"HTTP {r.status}")
            mime = r.headers.get("content-type", "").split(";")[0].strip().lower()
            guessed = mimetypes.guess_type(urlsplit(absolute).path)[0]
            if mime in ("application/octet-stream", "binary/octet-stream") and guessed in ALLOWED_MIME:
                mime = guessed
            if mime not in ALLOWED_MIME:
                raise NetworkError(f"Unsupported resource type: {mime}")
            body = safe_svg(r.body) if mime == "image/svg+xml" else r.body
            name = hashlib.sha256(body).hexdigest()[:20] + ALLOWED_MIME[mime]
            dest = self.directory / name
            dest.write_bytes(body)
            value = "assets/" + name
            self.urls[absolute] = value
            self.manifest.append(dict(url=absolute, file=value, bytes=len(body), type=mime, sha256=hashlib.sha256(body).hexdigest()))
            return value if css else ASSET_MARK + name
        except (ValueError, OSError) as e:
            self.issue("asset", f"Resource not imported ({urlsplit(absolute).hostname or 'unknown host'}): {str(e)[:180]}")
            self.urls[absolute] = "data:,"
            return "data:,"

    def _tokens(self, tokens, base):
        out = []
        for token in tokens:
            if token.type == "url":
                value = self.asset(token.value, base, css=True)
                out.extend(tinycss2.parse_component_value_list('url(' + self._quote(value) + ')'))
            elif token.type == "function" and token.lower_name == "url":
                value = tinycss2.serialize(token.arguments).strip().strip("\"'")
                value = self.asset(value, base, css=True)
                out.extend(tinycss2.parse_component_value_list('url(' + self._quote(value) + ')'))
            elif token.type == "function" and token.lower_name in ("expression", "-moz-binding"):
                continue
            else:
                if hasattr(token, "content"):
                    token.content = self._tokens(token.content, base)
                if hasattr(token, "arguments"):
                    token.arguments = self._tokens(token.arguments, base)
                out.append(token)
        return out

    @staticmethod
    def _quote(value):
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '') + '"'

    def stylesheet(self, css: str, base: str, depth=0) -> str:
        if len(css) > 4_000_000:
            self.issue("stylesheet", "A stylesheet exceeded the 4 MB limit.")
            return ""
        rules = tinycss2.parse_stylesheet(css, skip_comments=False, skip_whitespace=False)
        out = []
        for rule in rules:
            if rule.type == "error":
                self.issue("css-parse", "An invalid CSS rule was omitted.")
                continue
            if rule.type == "at-rule" and rule.lower_at_keyword == "charset":
                continue
            if rule.type == "at-rule" and rule.lower_at_keyword == "import":
                parts = [t for t in rule.prelude if t.type not in ("whitespace", "comment")]
                if not parts:
                    continue
                first = parts[0]
                href = getattr(first, "value", None)
                if first.type == "function" and first.lower_name == "url":
                    href = tinycss2.serialize(first.arguments).strip().strip("\"'")
                if not href or depth >= 4:
                    self.issue("css-import", "A nested CSS import could not be resolved.")
                    continue
                target = urljoin(base, href)
                if target in self.css_seen:
                    continue
                self.css_seen.add(target)
                try:
                    r = self.fetcher.get(target, follow=True)
                    if r.status != 200:
                        raise NetworkError(f"HTTP {r.status}")
                    imported = self.stylesheet(r.body.decode("utf-8", "replace"), r.url, depth+1)
                    tail = tinycss2.serialize(parts[1:]).strip()
                    if tail and ("layer" in tail or "supports" in tail):
                        self.issue("css-import-conditions", "A CSS import using layer()/supports() needs review.")
                        continue
                    out.append(f"@media {tail} {{\n{imported}\n}}" if tail else imported)
                except ValueError as e:
                    self.issue("css-import", str(e))
                continue
            if hasattr(rule, "prelude"):
                rule.prelude = self._tokens(rule.prelude, base)
            if getattr(rule, "content", None) is not None:
                rule.content = self._tokens(rule.content, base)
            out.append(tinycss2.serialize([rule]))
        return "".join(out)

    def inline(self, css, base):
        declarations = tinycss2.parse_declaration_list(css, skip_comments=True, skip_whitespace=True)
        out = []
        for d in declarations:
            if d.type != "declaration" or d.lower_name in ("behavior", "-moz-binding"):
                continue
            d.value = self._tokens(d.value, base)
            # Inline URLs are interpreted relative to the document, unlike stylesheet URLs.
            value = tinycss2.serialize([d]).replace('url("assets/', 'url("' + ASSET_MARK)
            out.append(value)
        return "".join(out)
