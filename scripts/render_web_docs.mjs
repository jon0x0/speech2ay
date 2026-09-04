import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const {marked}=await import(process.argv[2]||'marked');
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
function page(title,body,prefix=''){
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${title} · speech2ay</title><link rel="stylesheet" href="${prefix}style.css"></head><body><header class="site-header"><a class="brand" href="${prefix}index.html">speech2ay<span> / Audio Lab</span></a><nav><a href="${prefix}index.html">Play the demo</a><a href="https://github.com/jon0x0/speech2ay">GitHub ↗</a></nav></header><main class="article">${body}</main></body></html>`;
}
fs.mkdirSync(path.join(root,'web/docs'),{recursive:true});
for(const name of fs.readdirSync(path.join(root,'docs')).filter(n=>n.endsWith('.md'))){
  const text=fs.readFileSync(path.join(root,'docs',name),'utf8');
  const title=text.split('\n')[0].replace(/^# /,'');
  const html=marked.parse(text).replace(/href="(?:\.\/)?([^"/:]+)\.md(#[^"]*)?"/g,'href="$1.html$2"');
  fs.writeFileSync(path.join(root,'web/docs',name.replace('.md','.html')),page(title,html,'../'));
  if(name==='speaking-with-the-ts2068.md'){
    const article=html.replace(/href="([^"/:]+)\.html/g,'href="docs/$1.html');
    fs.writeFileSync(path.join(root,'web/article.html'),page(title,article));
  }
}
const credits=fs.readFileSync(path.join(root,'web/THIRD-PARTY.md'),'utf8');
fs.writeFileSync(path.join(root,'web/credits.html'),page('Credits and provenance',marked.parse(credits)));
console.log('Rendered article, guides and credits.');
