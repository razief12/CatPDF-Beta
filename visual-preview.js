(()=>{
for(const kind of ['delete','extract','duplicate','blank','metadata']){
 const form=document.querySelector(`.extra-form[data-kind="${kind}"]`);if(!form)continue;
 const file=form.elements.source, box=document.createElement('div');box.style.margin='12px 0';file.after(box);let generation=0,original={},activePdf=null,observer=null;
 if(kind==='metadata')form.querySelector('[data-meta-reset]').onclick=()=>{for(const [k,v] of Object.entries(original))form.elements[k].value=v;form.elements.removeAll.checked=false;};
 file.addEventListener('change',async()=>{const token=++generation;observer?.disconnect();observer=null;const previous=activePdf;activePdf=null;if(previous)previous.destroy().catch(()=>{});box.replaceChildren();const f=file.files[0];if(!f)return;let pdf;try{
 if(kind==='metadata'){const d=await PDFLib.PDFDocument.load(await f.arrayBuffer(),{updateMetadata:false});if(token!==generation)return;for(const [k,g] of [['title','getTitle'],['author','getAuthor'],['subject','getSubject'],['keywords','getKeywords'],['creator','getCreator'],['producer','getProducer']]){original[k]=d[g]()||'';form.elements[k].value=original[k];}form.querySelector('[data-meta-dates]').textContent=`Created: ${d.getCreationDate()?.toISOString()||'Unknown'} · Modified: ${d.getModificationDate()?.toISOString()||'Unknown'}`;return;}
 pdf=await loadPdfJs(await f.arrayBuffer());if(token!==generation)return;const grid=document.createElement('div');grid.className='thumb-grid';grid.style.cssText='display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:8px';box.append(grid);
 const sync=()=>{if(kind!=='blank')form.elements.pages.value=[...grid.querySelectorAll('.selected')].map(x=>x.dataset.page).join(',');};
 if(pdf.numPages>500)throw Error('Preview limit: 500 pages.');
 const source=pdf;activePdf=source;pdf=null;
 const render=async thumb=>{if(token!==generation||thumb.dataset.started)return;thumb.dataset.started='1';let page;try{page=await source.getPage(Number(thumb.dataset.page));if(token!==generation)return;const base=page.getViewport({scale:1}),viewport=page.getViewport({scale:Math.min(.32,180/Math.max(base.width,base.height))});const canvas=thumb.querySelector('canvas');canvas.width=Math.ceil(viewport.width);canvas.height=Math.ceil(viewport.height);await page.render({canvasContext:canvas.getContext('2d'),viewport}).promise;}catch(e){if(token===generation)thumb.querySelector('canvas').replaceWith(document.createTextNode('Preview unavailable'));}finally{page?.cleanup();}};
 let queue=Promise.resolve();const enqueue=thumb=>{queue=queue.then(()=>render(thumb)).catch(console.warn);};
 observer=typeof IntersectionObserver==='function'?new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){observer?.unobserve(e.target);enqueue(e.target);}},{rootMargin:'200px'}):null;
 for(let i=1;i<=source.numPages;i++){const thumb=document.createElement('div');thumb.className='thumb';thumb.dataset.page=i;thumb.innerHTML=`<canvas width="110" height="145"></canvas><span class="thumb-num">${i}</span>`;if(kind!=='blank')thumb.onclick=()=>{thumb.classList.toggle('selected');sync();};grid.append(thumb);if(observer)observer.observe(thumb);else enqueue(thumb);}
 
 if(kind==='blank'){const add=(n)=>{const b=document.createElement('button');b.type='button';b.textContent=n?`+ After ${n}`:'+ Before first';b.onclick=()=>{form.elements.after.value=n;for(const x of grid.querySelectorAll('button'))x.style.outline='';b.style.outline='2px solid #ec4899';};return b;};grid.prepend(add(0));for(const thumb of grid.querySelectorAll('.thumb'))thumb.append(add(Number(thumb.dataset.page)));}
 else{form.elements.pages.oninput=()=>{try{const selected=pageSelection(form.elements.pages.value,source.numPages);for(const thumb of grid.querySelectorAll('.thumb'))thumb.classList.toggle('selected',selected.has(Number(thumb.dataset.page)-1));}catch{} };}
 }catch(e){if(token===generation)box.textContent=e.message||'Preview failed';}finally{if(pdf)await pdf.destroy();}});
}
})();
