"""Generate real, escaped markup and separately editable React components.

No original JavaScript, eval, HTML-string injection or proprietary runtime is emitted.
Layout CSS is preserved rather than falsely described as a semantic redesign.
"""
from __future__ import annotations
import hashlib
import html
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import tinycss2
from .assets import ASSET_MARK, AssetCollector

HTML_TAGS = set("a abbr address article aside b bdi bdo blockquote br button caption cite code col colgroup data datalist dd del details dfn dialog div dl dt em fieldset figcaption figure footer form h1 h2 h3 h4 h5 h6 header hgroup hr i img input ins kbd label legend li main map mark menu meter nav ol optgroup option output p picture pre progress q rp rt ruby s samp search section select small source span strong sub summary sup table tbody td textarea tfoot th thead time tr u ul var video audio wbr".split())
SVG_TAGS = set("svg path circle ellipse rect line polyline polygon g defs symbol use clipPath mask linearGradient radialGradient stop pattern text tspan textPath title desc filter feGaussianBlur feOffset feBlend feColorMatrix feComponentTransfer feFuncR feFuncG feFuncB feFuncA feFlood feComposite feMerge feMergeNode feDropShadow".split())
VOID = set("area base br col embed hr img input link meta param source track wbr".split())
BOOLEAN = set("disabled hidden multiple required open checked selected readonly autofocus autoplay controls loop muted playsinline novalidate formnovalidate reversed ismap download".split()) - {"download"}
ATTR_MAP = {"class":"className","for":"htmlFor","tabindex":"tabIndex","readonly":"readOnly","maxlength":"maxLength","minlength":"minLength","colspan":"colSpan","rowspan":"rowSpan","cellpadding":"cellPadding","cellspacing":"cellSpacing","contenteditable":"contentEditable","spellcheck":"spellCheck","autocomplete":"autoComplete","autoplay":"autoPlay","playsinline":"playsInline","srcset":"srcSet","usemap":"useMap","accept-charset":"acceptCharset","http-equiv":"httpEquiv","datetime":"dateTime","viewbox":"viewBox","preserveaspectratio":"preserveAspectRatio","gradientunits":"gradientUnits","gradienttransform":"gradientTransform","patternunits":"patternUnits","patterncontentunits":"patternContentUnits","patterntransform":"patternTransform","clippathunits":"clipPathUnits","markerwidth":"markerWidth","markerheight":"markerHeight","refx":"refX","refy":"refY","textlength":"textLength","lengthadjust":"lengthAdjust","xlink:href":"xlinkHref","xmlns:xlink":"xmlnsXlink","stddeviation":"stdDeviation","filterunits":"filterUnits","primitiveunits":"primitiveUnits","colorinterpolationfilters":"colorInterpolationFilters"}

INTERACTIONS = r'''// Frameport-owned adapters only. No source-site scripts are executed.
const initialise = () => {
  document.querySelectorAll('button[aria-controls]').forEach(button => {
    const id = button.getAttribute('aria-controls');
    const target = id ? document.getElementById(id) : null;
    if (!target) return;
    const sync = () => {
      const expanded = button.getAttribute('aria-expanded') === 'true';
      target.hidden = !expanded;
      if (expanded && getComputedStyle(target).display === 'none') target.style.display = 'block';
      if (!expanded) target.style.removeProperty('display');
    };
    button.setAttribute('data-frameport-adapter', 'disclosure');
    button.addEventListener('click', () => {
      button.setAttribute('aria-expanded', String(button.getAttribute('aria-expanded') !== 'true'));
      sync();
    });
    // Preserve initial source styling; synchronise only on interaction.
    button.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        button.setAttribute('aria-expanded', 'false'); sync(); button.focus();
      }
    });
  });
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', event => {
      event.preventDefault();
      let note = form.querySelector('[data-frameport-form-note]');
      if (!note) {
        note = document.createElement('p'); note.setAttribute('role', 'status');
        note.setAttribute('data-frameport-form-note', ''); form.append(note);
      }
      note.textContent = 'Connect this form to your own submission service before publishing.';
    });
  });
};
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialise, {once:true});
else initialise();
'''

def safe_link(value: str) -> str:
    compact = re.sub(r"[\x00-\x20\x7f]+", "", value).lower()
    if compact.startswith(("javascript:", "vbscript:", "data:", "file:", "blob:")):
        return "#"
    if value.startswith(("#", "/", "./", "../")):
        return value
    try:
        return value if urlsplit(value).scheme.lower() in ("http", "https", "mailto", "tel") else "#"
    except ValueError:
        return "#"

def clean_tree(raw, prefix, assets: AssetCollector, base, texts, stats, depth=0):
    if not isinstance(raw, dict) or depth > 80:
        return None
    stats["nodes"] += 1
    if stats["nodes"] > 56000:
        raise ValueError("Site tree exceeds the compiler limit.")
    ident = prefix + "-" + re.sub(r"[^\w-]", "", str(raw.get("id", "node")))[:80]
    if "text" in raw:
        text = str(raw["text"])[:100000]
        texts[ident] = text
        return dict(id=ident, text=text)
    tag = str(raw.get("tag", "div"))
    if tag == "body":
        tag = "body"
    elif tag not in HTML_TAGS | SVG_TAGS:
        tag = "div"
    attrs = {}
    for k, v in dict(raw.get("attrs", {})).items():
        k = str(k).lower()
        if not re.fullmatch(r"[a-z][a-z0-9:_-]{0,80}", k) or k.startswith("on") or k in {"srcdoc","is","nonce","action","formaction","srcset","autofocus","integrity","ping"}:
            continue
        value = str(v)[:100000]
        if k == "style":
            if "!important" in value.lower(): assets.issue("react-important", "An inline !important declaration requires review in React; HTML preserves it.")
            value = assets.inline(value, base)
        elif k in ("src", "poster") or (k in ("href", "xlink:href") and tag in SVG_TAGS):
            value = assets.asset(value, base)
        elif k == "href":
            value = safe_link(value)
        attrs[k] = value
    if tag == "a" and attrs.get("target") == "_blank":
        attrs["rel"] = "noopener noreferrer"
    children = [clean_tree(c,prefix,assets,base,texts,stats,depth+1) for c in raw.get("children", [])[:7000]]
    return dict(id=ident, tag=tag, attrs=attrs, children=[c for c in children if c is not None])

def prepare_ir(captured, collector):
    texts = {}
    stats = Counter()
    pages = []
    for p in captured["pages"]:
        tree = clean_tree(p["tree"],p["key"],collector,p["url"],texts,stats)
        css = []
        for sheet in p["styles"][:150]:
            try:
                content = sheet.get("css")
                if content is None:
                    response = collector.fetcher.get(sheet["url"], follow=True)
                    if response.status != 200:
                        raise ValueError(f"Stylesheet HTTP {response.status}")
                    content = response.body.decode("utf-8", "replace")
                css.append(collector.stylesheet(content, sheet.get("base", p["url"])))
            except Exception as e:
                collector.issue("stylesheet", f"Stylesheet could not be imported: {str(e)[:160]}")
        html_attrs = {"class":str(p.get("htmlAttrs", {}).get("class", ""))[:10000], "style":collector.inline(str(p.get("htmlAttrs", {}).get("style", "")),p["url"])}
        pages.append({k:p[k] for k in ("key","url","title","description","lang","route","snapshots","warnings","framer")} | dict(tree=tree, css="\n".join(css), htmlAttrs=html_attrs))
    return dict(version=1,pages=pages,texts=texts,assets=collector.manifest,issues=captured["issues"]+collector.issues,discovered=captured["discovered"],nodes=stats["nodes"])

def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def page_file(page):
    return page["route"].strip("/") + "/index.html" if page["route"] != "/" else "index.html"

def root_prefix(page):
    return "../" * len([x for x in page["route"].split("/") if x])

def normal_path(url):
    u = urlsplit(url)
    return (u.netloc.lower(),re.sub(r"/index\.html?$", "/", u.path).rstrip("/") or "/")

def attrs_for(node, page, ir, react):
    attrs = dict(node.get("attrs", {}))
    prefix = "/" if react else root_prefix(page)
    for k in ("src","poster","href","xlink:href","style"):
        if k in attrs:
            attrs[k] = attrs[k].replace(ASSET_MARK, prefix + "assets/")
    if node.get("tag") == "a" and attrs.get("href", "").startswith(("http://","https://")):
        current = attrs["href"]
        dest = next((p for p in ir["pages"] if normal_path(p["url"]) == normal_path(current)), None)
        if dest:
            fragment = urlsplit(current).fragment
            attrs["href"] = (dest["route"] if react else root_prefix(page) + page_file(dest)) + ("#"+fragment if fragment else "")
    return attrs

def html_attrs(attrs):
    return "".join(f' {k}' if k in BOOLEAN else f' {k}="{html.escape(v,quote=True)}"' for k,v in attrs.items())

def to_html(node, page, ir):
    if "text" in node:
        return html.escape(ir["texts"].get(node["id"],node["text"]))
    tag = node["tag"]
    attrs = attrs_for(node,page,ir,False)
    attrs["data-fp-node"] = node["id"]
    opening = "<"+tag+html_attrs(attrs)+">"
    if tag in VOID:
        return opening
    return opening + "".join(to_html(c,page,ir) for c in node["children"]) + f"</{tag}>"

def react_style(value):
    out = {}
    important = False
    for d in tinycss2.parse_declaration_list(value,skip_comments=True,skip_whitespace=True):
        if d.type != "declaration":
            continue
        k = d.name
        if not k.startswith("--"):
            k = re.sub(r"-([a-z])",lambda m:m[1].upper(),k)
            if k.startswith("Ms"):
                k = "m"+k[1:]
        if d.important:
            important = True
        out[k] = tinycss2.serialize(d.value).strip()
    return json.dumps(out,ensure_ascii=True), important

def jsx_attrs(attrs, svg=False):
    parts = []
    for k,v in attrs.items():
        if k == "style":
            value, _ = react_style(v)
            parts.append(f"style={{{value} as React.CSSProperties}}")
            continue
        key = ATTR_MAP.get(k,k)
        if svg and not key.startswith(("data-","aria-")):
            key = re.sub(r"-([a-z])",lambda m:m[1].upper(),key)
        if ":" in key:
            continue
        if k in {"tabindex","colspan","rowspan","maxlength","minlength","size","span","start","rows","cols"} and re.fullmatch(r"-?\d+",v):
            parts.append(f"{key}={{{int(v)}}}")
        elif k in BOOLEAN:
            parts.append(f"{key}={{true}}")
        else:
            parts.append(f"{key}={{{json.dumps(v,ensure_ascii=True)}}}")
    return (" " + " ".join(parts)) if parts else ""

def component_name(node, used):
    label = node.get("attrs",{}).get("data-framer-name") or node["tag"]
    value = "".join(p[:1].upper()+p[1:] for p in re.findall(r"[a-zA-Z0-9]+",label))[:50] or "Section"
    if not value[0].isalpha():
        value = "Section"+value
    name = value
    i = 2
    while name in used:
        name = f"{value}{i}"
        i += 1
    used.add(name)
    return name

def to_jsx(node, page, ir, components, current=None, indent=2, svg=False):
    pad = " "*indent
    if "text" in node:
        return pad + '{content[' + json.dumps(node["id"]) + ']}'
    if node["id"] in components and node["id"] != current:
        return pad+f'<{components[node["id"]]} />'
    tag = node["tag"]
    svg = svg or tag == "svg"
    attrs = jsx_attrs(attrs_for(node,page,ir,True),svg)
    if tag in VOID or not node["children"]:
        return pad+f"<{tag}{attrs} />"
    children = "\n".join(to_jsx(c,page,ir,components,current,indent+2,svg) for c in node["children"])
    return pad+f"<{tag}{attrs}>\n{children}\n{pad}</{tag}>"

def generate(ir, root: Path):
    html_dir, react_dir = root/"html",root/"react"
    for out in (html_dir,react_dir):
        if out.exists(): shutil.rmtree(out)
        out.mkdir(parents=True)
    shutil.copytree(root/"assets",html_dir/"assets",dirs_exist_ok=True)
    shutil.copytree(root/"assets",react_dir/"public"/"assets",dirs_exist_ok=True)
    write(html_dir/"interactions.js", INTERACTIONS)
    write(react_dir/"src"/"interactions.ts", INTERACTIONS.replace("const initialise = () =>", "export const initialise = () =>").split("if (document.readyState")[0].replace("const id = button.getAttribute", "const id = button.getAttribute"))
    # This adapter is JavaScript with DOM type checking handled independently.
    (react_dir/"src"/"interactions.ts").rename(react_dir/"src"/"interactions.js")
    write(react_dir/"src"/"content"/"site.json",json.dumps(ir["texts"],indent=2,ensure_ascii=False))
    used_names = set()
    all_components = []
    page_names = []
    for page in ir["pages"]:
        prefix = root_prefix(page)
        file = page_file(page)
        meta = f'<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{html.escape(page["description"],quote=True)}"><title>{html.escape(page["title"])}</title>'
        css_path = f"styles/{page['key']}.css"
        # Stylesheets live under styles/, so resource paths need one parent segment.
        css = page["css"].replace('url("assets/', 'url("../assets/')
        write(html_dir/css_path,css)
        body = to_html(page["tree"],page,ir).replace("</body>",f'<script src="{prefix}interactions.js" defer></script></body>')
        attrs = dict(page["htmlAttrs"])
        attrs["lang"] = page["lang"]
        attrs["style"] = attrs["style"].replace(ASSET_MARK,prefix+"assets/")
        document = '<!doctype html>\n<html'+html_attrs(attrs)+f'><head>{meta}<link rel="stylesheet" href="{prefix}{css_path}"></head>{body}</html>\n'
        write(html_dir/file,document)
        selected = {}
        selected_nodes = []
        def collect(node,depth=0):
            if "text" in node: return
            candidate = node["tag"] in {"header","footer","section","nav"} or ("data-framer-name" in node["attrs"] and len(node["children"])>2)
            if depth > 0 and candidate and len(selected_nodes)<40:
                selected[node["id"]] = component_name(node,used_names)
                selected_nodes.append(node)
                return
            for c in node["children"]: collect(c,depth+1)
        collect(page["tree"])
        for node in selected_nodes:
            name = selected[node["id"]]
            code = 'import React from "react";\nimport content from "../content/site.json";\n\n'
            code += f'export default function {name}() {{\n  return (\n' + to_jsx(node,page,ir,selected,current=node["id"],indent=4) + '\n  );\n}\n'
            write(react_dir/f"src/components/{name}.tsx",code)
            all_components.append(dict(name=name,file=f"src/components/{name}.tsx",page=page["key"]))
        page_name = "Page"+page["key"][1:]
        page_names.append((page_name,page["route"]))
        imports = 'import React from "react";\nimport content from "../content/site.json";\n'
        for name in selected.values(): imports += f'import {name} from "../components/{name}";\n'
        body_jsx = "\n".join(to_jsx(c,page,ir,selected,indent=6) for c in page["tree"]["children"])
        write(react_dir/f"src/pages/{page_name}.tsx",imports+f'\nexport default function {page_name}() {{\n  return (\n    <>\n{body_jsx}\n    </>\n  );\n}}\n')
        # Root-serving React project. Body class/style are applied by the HTML entry.
        body_attrs = attrs_for(page["tree"],page,ir,True)
        react_attrs = dict(attrs)
        react_attrs["style"] = react_attrs["style"].replace(prefix+"assets/","/assets/")
        write(react_dir/file,'<!doctype html>\n<html'+html_attrs(react_attrs)+f'><head>{meta}<link rel="stylesheet" href="/styles/{page["key"]}.css"><style>#root{{display:contents}}</style></head><body'+html_attrs(body_attrs)+'><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>\n')
        write(react_dir/f"public/styles/{page['key']}.css",css)
    app = 'import React, { useEffect } from "react";\nimport { initialise } from "./interactions.js";\n'
    for name,_ in page_names: app += f'import {name} from "./pages/{name}";\n'
    app += '\nexport default function App() {\n  useEffect(() => { initialise(); }, []);\n  const path = window.location.pathname.replace(/index\\.html$/, "").replace(/\\/?$/, "/");\n'
    for name,route in page_names: app += f'  if (path === {json.dumps(route)}) return <{name} />;\n'
    app += '  return <main><h1>Page not found</h1><a href="/">Return home</a></main>;\n}\n'
    write(react_dir/"src/App.tsx",app)
    write(react_dir/"src/main.tsx",'import React from "react";\nimport { createRoot } from "react-dom/client";\nimport App from "./App";\n\nconst root = document.getElementById("root");\nif (!root) throw new Error("Missing app root");\ncreateRoot(root).render(<App />);\n')
    write(react_dir/"package.json",json.dumps(dict(name="frameport-export",version="1.0.0",private=True,type="module",scripts={"dev":"vite","build":"tsc --noEmit && vite build","preview":"vite preview"},dependencies={"react":"19.1.1","react-dom":"19.1.1"},devDependencies={"@types/react":"19.1.10","@types/react-dom":"19.1.9","typescript":"5.9.3","vite":"6.3.6"}),indent=2))
    write(react_dir/"tsconfig.json",json.dumps({"compilerOptions":{"target":"ES2022","lib":["ES2022","DOM","DOM.Iterable"],"module":"ESNext","moduleResolution":"Bundler","jsx":"react","strict":True,"esModuleInterop":True,"allowSyntheticDefaultImports":True,"resolveJsonModule":True,"skipLibCheck":True,"allowJs":True,"checkJs":False,"noEmit":True},"include":["src"]},indent=2))
    entries = {p["key"]:page_file(p) for p in ir["pages"]}
    write(react_dir/"vite.config.ts",'import { defineConfig } from "vite";\nexport default defineConfig({ build: { rollupOptions: { input: '+json.dumps(entries)+' } } });\n')
    write(react_dir/".gitignore","node_modules/\ndist/\n.env\n")
    write(html_dir/"README.md","# HTML export\n\nServe this folder with `python -m http.server 8080`, then open http://localhost:8080.\n\nPages, CSS and assets are local. Edit the HTML directly. Source scripts were removed. `interactions.js` contains only Frameport's disclosure and form-safety adapters. Native details/summary, links and CSS hover states remain native. Forms must be connected before publishing. Read `conversion-report.json` for tested coverage and unresolved issues.\n")
    write(react_dir/"README.md","# Editable React export\n\nUse Node 22. `npm install`, then `npm run dev`. Run `npm run build` before deployment.\n\nEdit text in `src/content/site.json`, sections in `src/components`, pages in `src/pages`, and layout CSS in `public/styles`. Assets are in `public/assets`. The Vite build has an HTML entry for each captured route; host the resulting `dist` at the domain root.\n\nNo Framer runtime or original scripts are imported. This is a reconstruction of rendered markup and CSS, not recovery of Framer's original source abstractions. Review inline `!important`, arbitrary interactions and every warning in the report. The HTML visual check is not a React production-build verification. No dependency lock is fabricated: commit your real lockfile after a successful install.\n")
    return dict(components=all_components,htmlDir=str(html_dir),reactDir=str(react_dir),textCount=sum(bool(t.strip()) for t in ir["texts"].values()))
