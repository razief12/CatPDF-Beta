import http from 'node:http';
const s=http.createServer((q,r)=>{r.writeHead(503,{'content-type':'text/html'});r.end('<html><body>Service Unavailable</body></html>')}); await new Promise(r=>s.listen(0,r));
const api='http://127.0.0.1:'+s.address().port;
// Verbatim logic from Patch 15 conversion.js:
try{ const health=await fetch(api+'/health',{cache:'no-store'}); const info=await health.json(); if(!health.ok||info.version!=='4.5.6.5.22')throw Error('Conversion server update pending. Please retry after deployment.'); }
catch(e){ console.log('Patch 15 gate, server returns HTML 503 during spin-up ->  user sees: "'+e.message+'"'); }
// Stale-but-working backend:
const s2=http.createServer((q,r)=>{r.writeHead(200,{'content-type':'application/json'});r.end(JSON.stringify({status:'ok',version:'4.5.6.5.20'}))}); await new Promise(r=>s2.listen(0,r));
try{ const health=await fetch('http://127.0.0.1:'+s2.address().port+'/health'); const info=await health.json(); if(!health.ok||info.version!=='4.5.6.5.22')throw Error('Conversion server update pending. Please retry after deployment.'); }
catch(e){ console.log('Patch 15 gate, healthy backend one build behind  ->  user sees: "'+e.message+'" (conversion blocked)'); }
s.close(); s2.close();
