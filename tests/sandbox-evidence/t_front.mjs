import http from 'node:http'; import vm from 'node:vm'; import fs from 'node:fs';
const win={}; const ctx=vm.createContext({window:win,document:{querySelectorAll:()=>[]},fetch,AbortController,AbortSignal,DOMException,TypeError,Error,setTimeout,clearTimeout,Date,JSON,Array,Math,Promise,console});
vm.runInContext(fs.readFileSync('p16/conversion.js','utf8'),ctx);
const H=win.CatConvertHelpers; let pass=0,total=0;
const chk=(l,ok,d='')=>{total++;if(ok)pass++;console.log((ok?'PASS ':'FAIL ')+l+(d?' | '+d:''))};
let mode='json', bootAt=0, hits=0;
const srv=http.createServer((q,r)=>{ if(q.url!=='/health'){r.writeHead(404);return r.end()} hits++;
  if(mode==='cold'&&Date.now()<bootAt){r.writeHead(503,{'content-type':'text/html'});return r.end('<html>Service Unavailable</html>')}
  if(mode==='hang'){return}            // never answers
  if(mode==='garbage'){r.writeHead(200);return r.end('<!doctype html>not json')}
  if(mode==='old'){r.writeHead(200,{'content-type':'application/json'});return r.end(JSON.stringify({status:'ok',version:'4.5.6.5.20'}))}
  r.writeHead(200,{'content-type':'application/json'});r.end(JSON.stringify({status:'ok',version:'4.5.6.5.23',kinds:['pdfdocx','docxpdf']})) });
await new Promise(r=>srv.listen(0,r)); const api='http://127.0.0.1:'+srv.address().port; const msgs=[]; const st=m=>msgs.push(m);
// 1 warm
mode='json'; let t=Date.now(); let info=await H.waitForServer(api,undefined,st); chk('warm server: immediate success',info.status==='ok'&&Date.now()-t<500);
// 2 cold start: 503 HTML for 3s then ok (the exact case the old await health.json() crashed on)
mode='cold'; bootAt=Date.now()+3000; hits=0; msgs.length=0; t=Date.now(); info=await H.waitForServer(api,undefined,st,{pauseMs:500,attemptMs:2000,maxMs:20000});
chk('cold start: retries through HTML 503 pages then succeeds',info.status==='ok'&&hits>=3,`hits=${hits}, ${((Date.now()-t)/1000).toFixed(1)}s`); chk('cold start: user sees wake-up progress',msgs.some(m=>m.includes('waking up')),msgs[0]);
// 3 garbage 200 body must not throw SyntaxError
mode='garbage'; try{await H.waitForServer(api,undefined,st,{pauseMs:100,attemptMs:500,maxMs:600});chk('garbage body handled',false)}catch(e){chk('non-JSON 200 -> clear timeout message, no JSON SyntaxError',/did not respond/.test(e.message)&&!/JSON|token/i.test(e.message),e.message.slice(0,90))}
// 4 hang: per-attempt timeout, bounded total
mode='hang'; t=Date.now(); try{await H.waitForServer(api,undefined,st,{pauseMs:100,attemptMs:300,maxMs:1200});chk('hang bounded',false)}catch(e){chk('hung server: bounded by maxMs, not forever',Date.now()-t<2500,`${Date.now()-t}ms`)}
// 5 cancel during wait is honoured promptly
mode='hang'; const ac=new AbortController(); setTimeout(()=>ac.abort(),400); t=Date.now(); try{await H.waitForServer(api,ac.signal,st,{pauseMs:100,attemptMs:5000,maxMs:60000});chk('cancel honoured',false)}catch(e){chk('user Cancel during cold start aborts promptly',Date.now()-t<1200,`${Date.now()-t}ms`)}
// 6 unreachable host
const dead=http.createServer(); await new Promise(r=>dead.listen(0,r)); const deadPort=dead.address().port; await new Promise(r=>dead.close(r));
t=Date.now(); try{await H.waitForServer('http://127.0.0.1:'+deadPort,undefined,st,{pauseMs:100,attemptMs:300,maxMs:800});chk('unreachable bounded',false)}catch(e){chk('unreachable server: clear message',/unreachable/.test(e.message),e.message.slice(0,80))}
// 7 version gate semantics
mode='old'; info=await H.waitForServer(api,undefined,st); let c=H.serverCompat(info,'pdfdocx'); chk('older backend (no kinds list): NOT blocked, warns',c.ok&&/differs/.test(c.warn),c.warn.trim());
mode='json'; info=await H.waitForServer(api,undefined,st); c=H.serverCompat(info,'pdfdocx'); chk('matching backend: ok, no warning',c.ok&&c.warn==='');
c=H.serverCompat(info,'pdfmd'); chk('backend genuinely missing converter: blocked with actionable message',!c.ok&&/does not support/.test(c.message));
// 8 error text
chk('HTTP 422 JSON detail shown verbatim',H.describeHttpError(422,'{"detail":"Conversion failed: File is not a zip file"}')==='Conversion failed: File is not a zip file');
chk('HTTP 502 HTML page -> status + restart hint',/Server error 502.*restarting/.test(H.describeHttpError(502,'<html>Bad Gateway</html>')));
chk('network TypeError -> CORS/restart hint',/Could not reach/.test(H.describeNetworkError(new TypeError('Failed to fetch'))));
srv.close(); console.log(`\nSUMMARY: ${pass}/${total} passed`); process.exit(pass===total?0:1);
