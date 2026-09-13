const finite = value => typeof value === 'number' && Number.isFinite(value);
const number = value => finite(value) ? value.toFixed(4) : '—';

export function currentFrameDetails(clip, frame, index) {
  const time=clip.times?.[index] ?? index/(clip.fps || 15);
  const measured=clip.measuredTimes;
  let sampling=clip.interpolated ? 'Interpolated playback' : 'Playback frame';
  if(measured?.length){
    let left=0;
    while(left+1<measured.length && measured[left+1]<=time+1e-8)left++;
    const source=i=>clip.sourceFrames?.[i] ?? i+1;
    if(Math.abs(time-measured[left])<1e-7) sampling=`Measured frame ${source(left)}`;
    else if(left===measured.length-1) sampling=`Hold of measured frame ${source(left)}`;
    else sampling=`Interpolated: measured ${source(left)} → ${source(left+1)}`;
  }
  const values=clip.signal?.[index] ?? Array.from(frame.values);
  const valid=values.filter(finite);
  const maximum=valid.length?Math.max(...valid):null;
  return {time,sampling,maximum,active:valid.filter(v=>v>.1).length,values,
    raw:clip.raw?.[index] ?? frame.rawVolts,baseline:clip.baseline?.[index] ?? frame.baseline};
}

export function createPlaybackDataPreview(root,onSelect) {
  const status=root.querySelector('[data-frame-status]');
  const summary=root.querySelector('[data-frame-summary]');
  const body=root.querySelector('tbody');let previousClip=null;let cells=[];
  return {update(clip,frame,index,playing,mapping,selected){
    const details=currentFrameDetails(clip,frame,index);
    if(previousClip!==clip){
      previousClip=clip;body.replaceChildren();cells=[];
      details.values.forEach((_,i)=>{
        const row=document.createElement('tr');const header=document.createElement('th');header.scope='row';
        const button=document.createElement('button');button.type='button';
        button.textContent=clip.sourceLabels?.[i] ?? clip.labels?.[i] ?? `N${String(i+1).padStart(3,'0')}`;
        button.title=clip.labels?.[i] ? `Inspect ${clip.labels[i]} on model` : 'Inspect on model';
        button.addEventListener('click',()=>onSelect(mapping?.[i] ?? i));header.append(button);row.append(header);
        const values=Array.from({length:3},()=>{const td=document.createElement('td');row.append(td);return td;});
        body.append(row);cells.push({row,values});
      });
    }
    status.textContent=`${playing?'Playing':'Paused'} · Frame ${index+1} / ${clip.frames.length} · ${details.time.toFixed(3)} s`;
    summary.textContent=`${details.sampling}\nPeak ${number(details.maximum)} · ${details.active} / ${details.values.length} nodes > 0.1`;
    cells.forEach(({row,values},i)=>{
      values[0].textContent=number(details.values[i]);values[1].textContent=number(details.raw?.[i]);values[2].textContent=number(details.baseline?.[i]);
      row.classList.toggle('active-response',finite(details.values[i])&&details.values[i]>.1);
      row.classList.toggle('selected-node',(mapping?.[i] ?? i)===selected);
    });
  }};
}
