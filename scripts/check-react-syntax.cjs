// Syntactic diagnostics are not a replacement for npm install + strict typecheck.
const fs = require('node:fs');
const path = require('node:path');
const ts = require(process.env.FRAMEPORT_TYPESCRIPT || 'typescript');
const root = process.argv[2];
if (!root) throw new Error('Usage: node scripts/check-react-syntax.cjs <export/react>');
function all(dir) { return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?all(path.join(dir,e.name)):[path.join(dir,e.name)]); }
const files=all(root).filter(p=>/\.(tsx?|js)$/.test(p));
let errors=[];
for(const file of files){
  const result=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,reportDiagnostics:true,compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext,jsx:ts.JsxEmit.React}});
  errors.push(...(result.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).map(d=>({file,message:ts.flattenDiagnosticMessageText(d.messageText,' ')})));
}
console.log(JSON.stringify({scope:'Generated React/TypeScript syntax only, not module resolution, strict types, dependencies or production build',files:files.length,errors},null,2));
if(errors.length)process.exit(1);
