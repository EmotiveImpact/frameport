import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseRoute,projectPath,safeReturnPath,viewPath} from '../web/dist/router.js';
const id='a'.repeat(32);
for(const [url,view] of [['/','overview'],['/convert','convert'],['/projects','history'],['/docs','docs'],['/settings','settings'],['/login','login']]){
 test(`route ${url}`,()=>{assert.equal(parseRoute(url).view,view);assert.equal(viewPath(view),url);});
}
for(const [segment,tab] of [['review','preview'],['source','source'],['content','content'],['verify','report'],['export','export']]){
 test(`project ${segment}`,()=>{const r=parseRoute(`/projects/${id}/${segment}`);assert.equal(r.id,id);assert.equal(r.tab,tab);assert.equal(projectPath(id,tab),`/projects/${id}/${segment}`);});
}
test('source deep link preserves selected file, target and viewport',()=>{const r=parseRoute(`/projects/${id}/source?file=src%2FApp.tsx&target=html&page=p2&width=390`);assert.equal(r.file,'src/App.tsx');assert.equal(r.target,'html');assert.equal(r.width,390);assert.equal(r.page,'p2');});
for(const url of ['/nonsense','/api/jobs',`/projects/${id}/evil`,'/projects/bad/source'])test(`unknown ${url}`,()=>assert.equal(parseRoute(url).view,'notfound'));
test('unsafe file and redirect are discarded',()=>{assert.equal(parseRoute(`/projects/${id}/source?file=../secret&width=100000`).file,'');assert.equal(safeReturnPath('//attacker.test'),'/projects');assert.equal(safeReturnPath('https://attacker.test'),'/projects');assert.equal(safeReturnPath('/settings'),'/settings');});
