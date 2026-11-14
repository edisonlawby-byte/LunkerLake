// In-game fish, old (Medium/Low) vs HQ (Ultra/High): side and 3/4 front each. Usage: node hqshot.js out.png sp1,sp2,...
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const OUT=process.argv[2],SPS=(process.argv[3]||'lmb').split(','),PORT=process.env.PORT||8123;
(async()=>{
  const browser=await chromium.launch({args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
  const ctx=await browser.newContext({viewport:{width:2000,height:300*SPS.length}});
  await ctx.addInitScript(()=>{window.__LLpause=true;});
  const page=await ctx.newPage();const logs=[];page.on('pageerror',e=>logs.push('PAGEERROR: '+e.message));page.on('console',m=>{if(m.type()==='error')logs.push(m.text())});
  const T=__dirname+'/node_modules/three';
  await page.route('**/*',r=>{const u=r.request().url();
    if(process.env.NOKIT&&u.includes('fish.glb'))return r.abort();
    if(u.includes('three.min.js'))return r.fulfill({status:200,contentType:'application/javascript',body:fs.readFileSync(T+'/build/three.min.js','utf8')});
    if(u.includes('GLTFLoader.js'))return r.fulfill({status:200,contentType:'application/javascript',body:fs.readFileSync(T+'/examples/js/loaders/GLTFLoader.js','utf8')});
    const m=/three@0\.128\.0\/(examples\/js\/.*)$/.exec(u);
    if(m&&fs.existsSync(T+'/'+m[1]))return r.fulfill({status:200,contentType:u.endsWith('.wasm')?'application/wasm':'application/javascript',body:fs.readFileSync(T+'/'+m[1])});
    if(u.startsWith('http://localhost'))return r.continue();return r.abort();});
  await page.goto(`http://localhost:${PORT}/index.html?lldebug`,{waitUntil:'commit'});
  await page.waitForFunction(()=>!!window.__LL,null,{timeout:180000});
  if(!process.env.NOKIT)await page.waitForFunction(()=>!!window.__LL.FishKit&&!!window.__LL.ScanKit,null,{timeout:120000});await page.waitForTimeout(2000);
  await page.evaluate(()=>{window.__LL.setQuality('ultra');window.__LL.loadHQKit();});await page.evaluate(()=>window.__LL.loadHQKit());
  await page.waitForFunction((SPS)=>SPS.every(sp=>window.__LL.HQKit[sp]),SPS,{timeout:120000});
  await page.evaluate((SPS)=>{for(const sp of SPS)window.__LL.makeFishMesh(sp);},SPS);await page.waitForTimeout(6000);
  const data=await page.evaluate(async(SPS)=>{
    const L=window.__LL;const W=500,H=300;
    const r=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});r.setSize(W,H);r.setClearColor(0x7a8e98);
    const out=[];
    for(const sp of SPS){
      const sc=new THREE.Scene();sc.add(new THREE.HemisphereLight(0xdfefff,0x40382c,.9));const d=new THREE.DirectionalLight(0xffffff,.9);d.position.set(1,2,1.5);sc.add(d);
      const row=[];
      for(const q of ['medium','ultra']){L.setQuality(q);const f=L.makeFishMesh(sp);f.position.y=0;sc.add(f);
      for(const [cx,cy,cz,lx] of [[0,0,1.25,0],[.95,.18,.7,.3]]){
        const cam=new THREE.PerspectiveCamera(cz>1?32:26,W/H,.01,10);cam.position.set(cx,cy,cz);cam.lookAt(lx,0,0);
        if(cy>1)cam.up.set(-1,0,0),cam.lookAt(.1,0,0);
        r.render(sc,cam);row.push(r.domElement.toDataURL('image/png'));}
      sc.remove(f);}
      out.push(row);}
    return out;},SPS);
  await page.setContent('<body style="margin:0;background:#222">'+data.map(row=>'<div style="display:flex">'+row.map(s=>`<img src="${s}">`).join('')+'</div>').join('')+'</body>');
  await page.waitForTimeout(300);
  await page.screenshot({path:OUT,fullPage:true});
  console.log(logs.slice(0,5).join('\n')||'ok');await browser.close();})();
