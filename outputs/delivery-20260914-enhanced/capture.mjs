import {chromium} from '/Users/a0000/.npm/_npx/420ff84f11983ee5/node_modules/playwright/index.mjs';
import fs from 'node:fs';
const root=process.cwd(),out=root+'/outputs/delivery-20260914-enhanced';
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});const page=await browser.newPage();page.on('pageerror',e=>console.error(e));
async function open(model){await page.goto('http://127.0.0.1:8766/outputs/delivery-20260914-enhanced/capture.html?model='+model);await page.waitForFunction(()=>window.ready,{timeout:60000});}
function save(name,url){fs.writeFileSync(out+'/'+name,Buffer.from(url.split(',')[1],'base64'));console.log(name);}
await open('human');const human=JSON.parse(fs.readFileSync(root+'/web/public/action-library/latest_human_arm_all_9_scenes.json'));
for(const k of human.keyframes)save('human_'+k.action+'_frame_'+k.index+'.png',await page.evaluate(async k=>window.capture('latest_human_arm_all_9_scenes',k.index),k));
await open('robot');const robot=JSON.parse(fs.readFileSync(root+'/web/public/action-library/delivery_robot_all.json'));
for(const k of robot.keyframes)save('robot_'+k.action+'_frame_'+k.index+'.png',await page.evaluate(async k=>window.capture('delivery_robot_all',k.index),k));
await open('finger');const library=JSON.parse(fs.readFileSync(root+'/web/public/delivery-final/finger-pairs.json'));
for(const seq of library)for(const k of seq.keyframes)for(const part of ['pair','0','1']){const name=`finger_${seq.id}_${String(k.position).padStart(2,'0')}_${k.orientation}_${part==='pair'?'AB':part==='0'?'A':'B'}_frame_${k.index}.png`;save(name,await page.evaluate(async({id,index,part})=>window.capturePair(id,index,part),{id:seq.id,index:k.index,part}));}
fs.writeFileSync(out+'/frames.json',JSON.stringify({human:human.keyframes,robot:robot.keyframes,finger:library.map(({id,keyframes})=>({id,keyframes})),resolution:[3200,3200],displayGain:1.8,frontLowSignalOpacity:.18,rearOpacity:1,mapping:'Exact frontend modules; source direction transforms already applied; sleeve angles 0 degrees'},null,2));await browser.close();
