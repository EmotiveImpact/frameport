/** Frameport bridge adapter. Read-only and intentionally SDK-injected.
 * Call createManifest(framer, url, includeCMS) from an official Framer plugin.
 * This preserves reference metadata; it is NOT a Framer canvas compiler.
 */
type Json = string | number | boolean | null | Json[] | {[key: string]: Json};
type Node = { id: string; name?: string; type?: string; [key:string]: unknown };
type Collection = {id:string; name?:string; getFields?:()=>Promise<unknown>; getItems?:()=>Promise<unknown>};
export interface ReadOnlyFramer {
  getProjectInfo(): Promise<unknown>;
  getCanvasRoot(): Promise<Node | null>;
  getChildren(id:string): Promise<Node[]>;
  getCollections(): Promise<Collection[]>;
}
function serialise(value: unknown): Json {
  // Framer objects may carry methods and circular SDK references. Copy only
  // JSON-compatible data with a finite depth; never execute getters/functions.
  const seen = new WeakSet<object>();
  function copy(v: unknown, depth=0): Json {
    if (v===null || typeof v==='boolean' || typeof v==='string') return v;
    if (typeof v==='number') return Number.isFinite(v)?v:null;
    if (typeof v!=='object' || depth>12 || seen.has(v)) return null;
    seen.add(v);
    if (Array.isArray(v)) return v.slice(0,2000).map(x=>copy(x,depth+1));
    const out: {[key:string]:Json}={};
    for (const [key,d] of Object.entries(Object.getOwnPropertyDescriptors(v))) {
      if (key.startsWith('_') || !('value' in d) || typeof d.value==='function') continue;
      out[key]=copy(d.value,depth+1);
    }
    return out;
  }
  return copy(value);
}
export async function createManifest(api: ReadOnlyFramer, publishedUrl:string, includeCMS=false) {
  const url=new URL(publishedUrl);
  if (!['https:','http:'].includes(url.protocol) || url.username || url.password) throw new Error('Enter the published HTTP(S) website address.');
  const warnings:string[]=[];
  const nodes:Array<{[key:string]:Json}>=[];
  const project=serialise(await api.getProjectInfo());
  const root=await api.getCanvasRoot();
  const seen=new Set<string>();
  async function visit(node:Node, parentId:string|null, depth:number) {
    if (seen.has(node.id)) return;
    if (nodes.length>=7000 || depth>80) throw new Error('Project exceeds the bridge node/depth limit.');
    seen.add(node.id);
    const attrs:{[key:string]:Json}={id:node.id,parentId};
    for (const key of ['name','type','width','height','position','layout','gap','padding','backgroundColor','borderRadius','visible']) {
      try { if (node[key]!==undefined) attrs[key]=serialise(node[key]); } catch { warnings.push('Could not read '+key+' on '+node.id); }
    }
    nodes.push(attrs);
    // Not every node can have children. No project mutation APIs are called.
    let children:Node[]=[];
    try { children=await api.getChildren(node.id); } catch { return; }
    for (const child of children) await visit(child,node.id,depth+1);
  }
  if (root) await visit(root,null,0);
  const collections:Array<{[key:string]:Json}>=[];
  if (includeCMS) {
    for (const c of (await api.getCollections()).slice(0,100)) {
      if (!c.getItems || !c.getFields) {warnings.push('Collection '+c.id+' is not readable through this bridge.');continue;}
      try {collections.push({id:c.id,name:c.name||'',fields:serialise(await c.getFields()),items:serialise(await c.getItems())});}
      catch {warnings.push('Could not export collection '+c.id+'.');}
    }
  }
  const manifest={schema:'frameport.bridge.v1',publishedUrl:url.href,project:project&&typeof project==='object'&&!Array.isArray(project)?project:{},nodes,collections,warnings:warnings.slice(0,200)};
  if(new TextEncoder().encode(JSON.stringify(manifest)).length>1_000_000)throw new Error('Manifest exceeds 1 MB. Export without CMS or reduce the project scope.');
  return manifest;
}
export function downloadManifest(manifest: Awaited<ReturnType<typeof createManifest>>) {
  const url=URL.createObjectURL(new Blob([JSON.stringify(manifest,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download='frameport-manifest.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
