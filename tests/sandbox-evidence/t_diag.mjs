import http from 'node:http'; import vm from 'node:vm'; import fs from 'node:fs'; import {execFileSync} from 'node:child_process';
const html=fs.readFileSync('p16/diagnose.html','utf8'); const js=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const win={}; vm.runInContext(js,vm.createContext({window:win,document:{getElementById:()=>null},TextEncoder,TextDecoder,atob,fetch,FormData,File,Blob,AbortController,setTimeout,clearTimeout,Date,JSON,Uint8Array,Array,Object,console,String,Promise}));
const D=win.CatDiag; let uploads=[];
const srv=http.createServer(async(q,r)=>{ if(q.url==='/health'){r.writeHead(200,{'content-type':'application/json','access-control-allow-origin':'*'});return r.end(JSON.stringify({status:'ok',version:'4.5.6.5.23',kinds:['pdftxt','pdfdocx']}))}
  const chunks=[];for await(const c of q)chunks.push(c);const buf=Buffer.concat(chunks);const m=q.url.match(/\/convert\/(\w+)/);
  const i=buf.indexOf('%PDF-'),j=buf.lastIndexOf('%%EOF');const pdf=buf.subarray(i,j+6);const f=`diag_up/${uploads.length}_${m[1]}.pdf`;fs.writeFileSync(f,pdf);uploads.push({kind:m[1],file:f,ct:q.headers['content-type']});
  if(m[1]==='pdftxt'){const t=execFileSync('pdftotext',[f,'-']);r.writeHead(200,{'access-control-allow-origin':'*'});return r.end(t)}
  r.writeHead(422,{'content-type':'application/json','access-control-allow-origin':'*'});r.end(JSON.stringify({detail:'mock: not implemented'}))});
await new Promise(r=>srv.listen(0,r)); const api='http://127.0.0.1:'+srv.address().port; const lines=[];
const rep=await D.run(api,m=>lines.push(m)); srv.close();
let pass=0,total=0;const chk=(l,ok,d='')=>{total++;if(ok)pass++;console.log((ok?'PASS ':'FAIL ')+l+(d?' | '+d:''))};
chk('multipart upload sent with file field',uploads.length>=4&&uploads.every(u=>/multipart\/form-data/.test(u.ct)),uploads.map(u=>u.kind).join(','));
const by=n=>uploads.find(u=>u.file.includes(n));
// independent validation of generated fixtures
const py=`import sys;from pypdf import PdfReader;r=PdfReader(sys.argv[1]);print(len(r.pages))`;
const pages=f=>+execFileSync('python3',['-c',py,f]).toString().trim();
const imgs=f=>execFileSync('pdfimages',['-list',f]).toString().trim().split('\n').slice(2).length;
const txt=f=>execFileSync('pdftotext',[f,'-']).toString();
const u=uploads.filter(x=>x.kind==='pdfdocx');
chk('text fixture: valid PDF, 1 page, tokens extractable by poppler',pages(u[0].file)===1&&txt(u[0].file).includes('CATPDF-TEXT-48213')&&txt(u[0].file).includes('1,234.50 qty 007'));
chk('scan fixture: valid PDF, 1 page, 1 image, NO text layer',pages(u[1].file)===1&&imgs(u[1].file)===1&&txt(u[1].file).trim()==='');
chk('mixed fixture: 2 pages, text on p1, image on p2',pages(u[2].file)===2&&imgs(u[2].file)===1&&txt(u[2].file).includes('CATPDF-TEXT-48213'));
const c=Object.fromEntries(rep.checks.map(x=>[x.name,x]));
chk('diag: TXT check PASSes against real poppler extraction',c['Text-only PDF → TXT: HTTP 200 AND content present']?.result==='PASS');
chk('diag: reports FAIL (not PASS) when server returns HTTP 422',c['Text-only PDF → Word: content present']?.result==='FAIL'&&/422/.test(c['Text-only PDF → Word: content present'].detail),c['Text-only PDF → Word: content present']?.detail);
chk('diag: health timing + version captured',rep.health.info.version==='4.5.6.5.23'&&rep.health.attempts.length>=1);
console.log(`\nSUMMARY: ${pass}/${total} passed`);process.exit(pass===total?0:1);
