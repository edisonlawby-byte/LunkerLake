// Gameplay check for the HQ fish: quality tiers swap meshes live, no page errors, frame times. node hqgame.js
const {chromium}=require('playwright');const fs=require('fs');const T=__dirname+'/node_modules/three';
(async()=>{const browser=await chromium.launch({args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
  const page=await (await browser.newContext({viewport:{width:1280,height:800}})).newPage();const logs=[];page.on('pageerror',e=>logs.push('PAGEERROR '+e.message));
  page.on('console',m=>{if(m.type()==='error')logs.push('console '+m.text())});
  await page.route('**/*',r=>{const u=r.request().url();
    if(u.includes('three.min.js'))return r.fulfill({status:200,contentType:'application/javascript',body:fs.readFileSync(T+'/build/three.min.js')});
    const m=/three@0\.128\.0\/(examples\/js\/.*)$/.exec(u);if(m)return r.fulfill({status:200,contentType:u.endsWith('.wasm')?'application/wasm':'application/javascript',body:fs.readFileSync(T+'/'+m[1])});
    if(u.startsWith('http://localhost'))return r.continue();return r.abort();});
  await page.goto('http://localhost:8123/index.html?lldebug',{waitUntil:'commit'});
  await page.waitForFunction(()=>window.__LL&&window.__LL.FishKit&&window.__LL.ScanKit,null,{timeout:180000});
  await page.evaluate(()=>window.__LL.setQuality('ultra',true));
  await page.waitForTimeout(8000);
  const count=()=>page.evaluate(()=>{const fs=window.__LL.fishes;const by={};for(const f of fs){const k=f.mesh.userData.hq?'hq':f.mesh.userData.scan?'scan':'std';by[k]=(by[k]||0)+1;}
    return JSON.stringify({q:window.__LL.G&&document.querySelector('[data-set="quality:ultra"]')?'':'',by,species:[...new Set(fs.map(f=>f.sp))].join(',')});});
  console.log('ultra ',await count());
  // put the HQ species in the water (replace the first fish of each) to check the live swap
  await page.evaluate(()=>{const L=window.__LL;['sm','cr','br'].forEach((sp,i)=>{const f=L.fishes[i];if(!f)return;const o=f.mesh;f.sp=sp;const m=L.makeFishMesh(sp);m.position.copy(o.position);m.scale.copy(o.scale);o.parent.add(m);o.parent.remove(o);f.mesh=m;});});
  console.log('placed',await count());
  await page.evaluate(()=>window.__LL.setQuality('medium',true));await page.waitForTimeout(500);console.log('medium',await count());
  await page.evaluate(()=>window.__LL.setQuality('high',true));await page.waitForTimeout(500);console.log('high  ',await count());
  // frame time with HQ fish swimming
  const ms=await page.evaluate(async()=>{const t0=performance.now();let n=0;await new Promise(res=>{const f=()=>{n++;if(performance.now()-t0<4000)requestAnimationFrame(f);else res();};requestAnimationFrame(f);});return (performance.now()-t0)/n;});
  console.log('avg frame ms (software GL)',ms.toFixed(1));
  // a close look in the scene: bring an HQ fish in front of the camera
  await page.evaluate(()=>{const L=window.__LL;const cam=L.camera;const dir=new THREE.Vector3();cam.getWorldDirection(dir);
    ['sm','cr','br'].forEach((sp,i)=>{const f=L.fishes[i];const p=cam.position.clone().add(dir.clone().multiplyScalar(2.2));p.x+=(i-1)*.75;p.y=Math.max(p.y-.3,0.05);
      f.mesh.position.copy(p);f.mesh.scale.setScalar(.5);f.mesh.rotation.set(0,Math.atan2(dir.x,dir.z)+Math.PI/2+.25,0);f.mesh.visible=true;f.state='debug';});});
  await page.waitForTimeout(800);await page.screenshot({path:process.argv[2]||'/tmp/hqgame.png'});
  console.log(logs.join('\n')||'no page errors');await browser.close();})();
