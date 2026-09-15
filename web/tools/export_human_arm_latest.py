"""Publish the canonical, already processed Human arm CSV without transforming samples."""
from pathlib import Path
import csv, hashlib, json, math
from itertools import groupby
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'meshy_arm_finger_delivery_20260914/human_arm/uploads/00_ALL_9_SCENES_FRONT_FACING_3X_SLOW_SMOOTH_MAPPING_FIXED_UPLOAD.csv'
OUT=ROOT/'web/public/action-library'

def export():
 with SOURCE.open(encoding='utf-8-sig',newline='') as f:
  reader=csv.DictReader(f);labels=[f'N{i:03}' for i in range(1,97)]
  assert [k for k in reader.fieldnames if k.startswith('N')]==labels
  rows=list(reader)
 times=[float(r['source_elapsed_s']) for r in rows]
 assert all(abs(t-i*.05)<1e-6 for i,t in enumerate(times))
 values=[[float(r[n]) for n in labels] for r in rows]
 assert all(math.isfinite(v) and 0<=v<=1 for row in values for v in row)
 groups=[];offset=0
 for label,group in groupby(rows,key=lambda r:r['action_label']):
  part=list(group);groups.append((label,offset,offset+len(part)));offset+=len(part)
 assert len(groups)==9 and len({g[0] for g in groups})==9
 sha=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
 keys=list(csv.DictReader((SOURCE.parent.parent/'keyframes/human_arm_keyframes.csv').open(encoding='utf-8-sig')))
 for key in keys:
  index=int(key['key_frame_0based']);a=int(key['segment_start_frame_0based']);b=int(key['segment_end_frame_0based'])
  assert abs(times[index]-float(key['combined_time_s']))<1e-6
  assert abs(sum(values[index])-max(map(sum,values[a:b+1])))<1e-6
  frame=next(csv.DictReader((SOURCE.parent.parent/'keyframes'/key['keyframe_csv']).open(encoding='utf-8-sig')))
  assert values[index]==[float(frame[n]) for n in labels]

 manifest=json.loads((OUT/'manifest.json').read_text())
 manifest=[m for m in manifest if m['sensorCount']!=96]
 entries=[]
 for label,start,end in [('All 9 scenes · 3× slow',0,len(rows)),*groups]:
  combined=start==0 and end==len(rows)
  ident='latest_human_arm_'+('all_9_scenes' if combined else label[:2])
  title=label if combined else label.replace('_96nodes','').replace('_MAPPING_FIXED','').replace('_CONTINUOUS_CORE','').replace('_',' ')
  record=dict(id=ident,label=title,group='Human arm · Latest · 2026-09-14',action='all_scenes' if combined else rows[start]['action_id'],sensorCount=96,source=str(SOURCE.relative_to(ROOT)),sourceSha256=sha,sourceRowRange=[start+2,end+1],originalFrames=None,fps=20,interpolated=True,dataKind='processed-signal',labels=labels,sourceLabels=labels,coordinates=[{'row':i//8+1,'column':i%8+1} for i in range(96)],times=[round(t-times[start],6) for t in times[start:end]],sourceTimes=times[start:end],sourceFrames=[r['source_frame'] for r in rows[start:end]],phases=[r['phase'] for r in rows[start:end]],actionIds=[r['action_id'] for r in rows[start:end]],rotationRows=[r['rotation_rows'] for r in rows[start:end]],signal=values[start:end],signalLayer='Signal Combined',processing='Source already front-facing, mapping-fixed, smoothed and 3× slow. N001–N096 and all values preserved exactly; no extra rotation, scaling or interpolation.',timingSource='source_elapsed_s (supplied 20 FPS display timeline)')
  record['keyframes']=[{'index':int(k['key_frame_0based'])-start,'sourceIndex':int(k['key_frame_0based']),'action':k['action_id']} for k in keys if start<=int(k['key_frame_0based'])<end]
  (OUT/f'{ident}.json').write_text(json.dumps(record,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
  entries.append({k:record[k] for k in ['id','label','group','action','sensorCount','source','dataKind']}|{'url':f'/action-library/{ident}.json','frames':end-start})
 (OUT/'manifest.json').write_text(json.dumps(entries+manifest,ensure_ascii=False,indent=2)+'\n')
 (ROOT/'human_arm/latest-data-manifest.json').write_text(json.dumps({'source':str(SOURCE.relative_to(ROOT)),'sha256':sha,'frames':len(rows),'durationSeconds':times[-1],'sensorCount':96,'scenes':[{'label':label,'firstRow':start+2,'lastRow':end+1,'frames':end-start} for label,start,end in groups]},indent=2)+'\n')
 print(f'Exported latest Human arm: {len(rows)} unchanged frames, 9 scenes + combined playback, {times[-1]} seconds.')

if __name__=='__main__':export()
