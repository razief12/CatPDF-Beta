const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('index.html','utf8').replace(/\r\n/g,'\n');
const start=html.indexOf("document.addEventListener('click', e => {\n  const panel = e.target.closest('.panel');");
assert.ok(start>=0);const end=html.indexOf('}, true);',start)+9;
let guard;vm.runInNewContext(html.slice(start,end),{document:{addEventListener:(type,fn,capture)=>{assert.equal(type,'click');assert.equal(capture,true);guard=fn}}});
for(const [state,cancel,blocked] of [['processing',true,false],['loading',true,false],['processing',false,true],['loading',false,true],['idle',false,false]]){
 let prevented=0,stopped=0;const panel={dataset:{[state]:'true'}};
 guard({target:{closest:s=>s==='.panel'?panel:cancel?{}:null},preventDefault:()=>prevented++,stopImmediatePropagation:()=>stopped++});
 assert.equal(prevented,Number(blocked));assert.equal(stopped,Number(blocked));console.log('PASS:',state,cancel?'Cancel':'other control');
}
