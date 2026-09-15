"""Publish the final Robot arm and independently mapped Finger A/B delivery."""
from pathlib import Path
import csv,json,hashlib,shutil,math
ROOT=Path(__file__).resolve().parents[2];SRC=ROOT/'meshy_arm_finger_delivery_Final';OUT=ROOT/'web/public/delivery-final';OUT.mkdir(exist_ok=True)
def read(path,count):
 rows=list(csv.DictReader(path.open(encoding='utf-8-sig')));labels=[f'N{i:03}' for i in range(1,count+1)]
 assert [k for k in rows[0] if k.startswith('N')]==labels
 values=[[float(r[n]) for n in labels] for r in rows];times=[float(r['action_elapsed_s']) for r in rows]
 assert all(math.isfinite(v) and 0<=v<=1 for r in values for v in r)
 assert all(abs(t-i*.05)<1e-6 for i,t in enumerate(times))
 return rows,values,times,labels
keyframes=list(csv.DictReader((SRC/'finger/website_key_frames.csv').open(encoding='utf-8-sig')))
pairs=[]
for sequence,label in [('all8','All 8 · Palm/front'),('group1','Group 1 · Palm/back/back/palm'),('group2','Group 2 · Palm/back/back/palm')]:
 pair={'id':sequence,'label':label,'keyframes':[]}
 for sleeve in ['A','B']:
  p=next((SRC/'finger').glob(f'finger_{sequence}_*_{sleeve}_18node.csv'));rows,values,times,labels=read(p,18)
  assert p.stat().st_size<3*1024*1024
  shutil.copyfile(p,OUT/p.name);pair[sleeve]='/delivery-final/'+p.name
  pair[sleeve+'Sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
  if sleeve=='A':pair['frames']=len(rows)
  else:assert pair['frames']==len(rows)
 for k in keyframes:
  if k['sequence']!=sequence:continue
  index=int(k['website_key_frame_0based']);assert abs(times[index]-float(k['website_time_s']))<1e-6
  pair['keyframes'].append({'index':index,'time':times[index],'label':f"{k['position']} · {k['orientation']} · {times[index]:.2f} s",'orientation':k['orientation'],'position':int(k['position']),'actionA':k['sleeve_A_action'],'actionB':k['sleeve_B_action']})
 pairs.append(pair)
(OUT/'finger-pairs.json').write_text(json.dumps(pairs,indent=2)+'\n')
p=SRC/'arm/robot_arm_RB004_RB003_RB001_front_facing_combined_upload.csv';rows,values,times,labels=read(p,132)
keys=list(csv.DictReader((SRC/'arm/keyframes/arm_keyframes.csv').open(encoding='utf-8-sig')))
records=[('all','All 3 · Front-facing',0,len(rows)-1)]
for key in keys:
 a,b,index=[int(key[n]) for n in ['segment_start_frame_0based','segment_end_frame_0based','key_frame_0based']]
 sums=[sum(r) for r in values[a:b+1]];assert sums.index(max(sums))+a==index
 assert abs(times[index]-float(key['combined_time_s']))<1e-6
 single=next(csv.DictReader((SRC/'arm/keyframes'/key['keyframe_csv']).open(encoding='utf-8-sig')))
 assert [float(single[n]) for n in labels]==values[index]
 records.append((key['action_id'],key['action_id']+' · '+key['action_type'],a,b))
catalog=ROOT/'web/public/action-library';manifest=[m for m in json.loads((catalog/'manifest.json').read_text()) if m['sensorCount']!=132];entries=[]
for action,label,a,b in records:
 ident='delivery_robot_'+action
 clip=dict(id=ident,label=label,group='Robot arm · Final delivery',action=action,sensorCount=132,source=str(p.relative_to(ROOT)),sourceSha256=hashlib.sha256(p.read_bytes()).hexdigest(),fps=20,originalFrames=None,interpolated=True,dataKind='processed-signal',signalLayer='Signal Combined',labels=labels,sourceLabels=labels,signal=values[a:b+1],times=[round(t-times[a],6) for t in times[a:b+1]],sourceTimes=times[a:b+1],coordinates=[{'row':i//12+1,'column':i%12+1} for i in range(132)],processing='Final front-facing Signal Combined; source values and mapping preserved, no additional transformations.',keyframes=[{'index':int(k['key_frame_0based'])-a,'action':k['action_id'],'sourceIndex':int(k['key_frame_0based'])} for k in keys if a<=int(k['key_frame_0based'])<=b])
 (catalog/f'{ident}.json').write_text(json.dumps(clip,separators=(',',':'))+'\n')
 entries.append({k:clip[k] for k in ['id','label','group','action','sensorCount','source','dataKind']}|{'url':f'/action-library/{ident}.json','frames':b-a+1})
(catalog/'manifest.json').write_text(json.dumps(entries+manifest,indent=2)+'\n')
(OUT/'robot-keyframes.json').write_text(json.dumps(keys,indent=2)+'\n')
print('Final delivery verified: Robot arm 938 frames / 3 keys; Finger 3 A+B pairs / 16 paired keys.')
