import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source = fs.readFileSync(new URL('./src/main.js', import.meta.url), 'utf8');
const start = source.indexOf('let sharedCatalogMutation = 0;');
const end = source.indexOf("document.querySelector('#refresh-shared-uploads').addEventListener", start);
const dataset = {id:'shared_visitor',shareId:'visitor',sensorCount:18,label:'Visitor CSV'};
const parsed = {frames:[{time:0}]};
const state = {hostedDatasets:new Map([['builtin',{id:'builtin'}],['shared_old',{id:'shared_old',shareId:'old'}],['shared_visitor',{...dataset,parsed}]])};
const button = {disabled:false}; const status = {textContent:''};
let pending, rendered, actions;
const context = vm.createContext({state,elements:{playbackSelect:{value:'shared_visitor'}},document:{querySelector:id=>id.includes('status')?status:button},fetch:()=>new Promise(resolve=>{pending=resolve;}),uploadError:async()=> 'offline',renderHostedPlaybackOptions:id=>{rendered=id;},updateUploadActions:value=>{actions=value;}});
vm.runInContext(source.slice(start,end),context);
let request=vm.runInContext('refreshSharedUploads()',context);
pending({ok:true,json:async()=>[dataset]});await request;
assert(state.hostedDatasets.has('builtin'));
assert(!state.hostedDatasets.has('shared_old'));
assert.equal(state.hostedDatasets.get(dataset.id).parsed,parsed);
assert.equal(rendered,dataset.id);
assert.match(status.textContent,/1 shared uploads/);
assert.equal(button.disabled,false);
// An older list response cannot hide a recording uploaded while it was in flight.
request=vm.runInContext('refreshSharedUploads()',context);
vm.runInContext('sharedCatalogMutation += 1',context);
pending({ok:true,json:async()=>[]});await request;
assert(state.hostedDatasets.has(dataset.id));
// Service failure retains the existing catalog and enables retry.
request=vm.runInContext('refreshSharedUploads()',context);
pending({ok:false});await request;
assert(state.hostedDatasets.has(dataset.id));assert.match(status.textContent,/unavailable/);assert.equal(button.disabled,false);
// Another visitor deleting the selected upload removes it without restarting playback.
request=vm.runInContext('refreshSharedUploads()',context);
pending({ok:true,json:async()=>[]});await request;
assert(!state.hostedDatasets.has(dataset.id));assert.equal(actions,null);
console.log('Shared upload refresh: merge, selection, parsed playback cache, deletion, racing mutation, and failure recovery passed.');
