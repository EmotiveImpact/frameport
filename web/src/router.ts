/** URL state is the source of truth. Every route also has a server entrypoint. */
export type View = 'overview'|'convert'|'history'|'project'|'docs'|'settings'|'login'|'notfound';
export type Tab = 'preview'|'source'|'content'|'report'|'export';
export interface Route {view:View; tab:Tab; id?:string; file:string; target:'react'|'html'; page:string; width:number}
const segments: Record<string,Tab> = {review:'preview',source:'source',content:'content',verify:'report',export:'export'};
const paths: Record<string,string> = {overview:'/',convert:'/convert',history:'/projects',docs:'/docs',settings:'/settings',login:'/login'};
export const tabSegment: Record<Tab,string> = {preview:'review',source:'source',content:'content',report:'verify',export:'export'};
export function parseRoute(input:string):Route {
  const route:Route={view:'notfound',tab:'preview',file:'',target:'react',page:'p0',width:1440};
  try {
    const url=new URL(input,'https://frameport.invalid');
    const path=url.pathname.replace(/\/$/,'')||'/';
    const staticView=Object.entries(paths).find(([,p])=>p===path)?.[0];
    if(staticView)route.view=staticView as View;
    else {
      const match=path.match(/^\/projects\/([a-f0-9]{32})(?:\/(review|source|content|verify|export))?$/);
      if(match){route.view='project';route.id=match[1];route.tab=segments[match[2]||'review'];}
    }
    const file=url.searchParams.get('file')||'';
    if(file.length<=400&&!file.includes('..')&&!/[\x00-\x1f\\]/.test(file))route.file=file;
    route.target=url.searchParams.get('target')==='html'?'html':'react';
    const page=url.searchParams.get('page')||'p0';if(/^p\d+$/.test(page))route.page=page;
    const width=Number(url.searchParams.get('width'));if([390,540,768,1024,1440].includes(width))route.width=width;
  } catch { /* Invalid paths render a proper not-found state. */ }
  return route;
}
export function viewPath(view:string):string{return paths[view]||'/';}
export function projectPath(id:string,tab:string='preview'):string {
  if(!/^[a-f0-9]{32}$/.test(id))throw new Error('Invalid project identifier');
  return `/projects/${id}/${tabSegment[tab as Tab]||'review'}`;
}
export function safeReturnPath(path:string):string {
  if(!path.startsWith('/')||path.startsWith('//'))return '/projects';
  return parseRoute(path).view==='notfound'?'/projects':path;
}
