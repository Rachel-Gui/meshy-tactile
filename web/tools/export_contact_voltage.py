"""Append the three already-interpolated contact-voltage display recordings."""
from pathlib import Path
import csv,json,hashlib
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'web/public/action-library'
source=ROOT/'robot_arm/action_library/contact_voltage_display'
manifest=json.loads((OUT/'manifest.json').read_text())
manifest=[x for x in manifest if not x['id'].startswith('contact_robot_')]
labels=[f'N{i:03}' for i in range(1,133)]
parts=[];provenance=[]
for ident in ['RB004','RB003','RB001']:
 p=next(p for p in source.glob(ident+'_*.csv') if 'combined' not in p.name)
 rows=list(csv.DictReader(p.open(encoding='utf-8-sig')));parts+=rows
 volts=[[float(r[n]) if r[n].strip() else None for n in labels] for r in rows]
 times=[float(r['display_time_s']) for r in rows]
 assert all(abs(t-i*.05)<1e-6 for i,t in enumerate(times))
 assert all(sum(v is not None for v in row)==int(r['active_node_count']) for row,r in zip(volts,rows))
 # Fixed common voltage scale for all three clips; display intensity is not force.
 signal=[[None if v is None else max(0,min(1,1-v/2.1)) for v in row] for row in volts]
 record=dict(id='contact_robot_'+ident,label=f'{ident} · {rows[0]["action_type"]} · Contact voltage',group='Robot arm · Contact voltage',action=rows[0]['action_type'],sensorCount=132,source=str(p.relative_to(ROOT)),originalFrames=None,fps=20,interpolated=True,times=times,labels=labels,sourceLabels=labels,coordinates=[{'row':i//12+1,'column':i%12+1} for i in range(132)],signal=signal,raw=volts,signalLayer='Contact Voltage (V)',dataKind='contact-voltage',voltageRange=[0,2.1],processing='Already-interpolated display data. Lower voltage = stronger contact. Color intensity = 1 − V / 2.1; not a calibrated force. Blank = masked, not zero volts. Source display transforms are already applied; no extra flip or shift.',sourceProcessing='RB004: cumulative minimum voltage and vertical flip; RB003: shifted up one crossing level; node order retained as supplied.',timingSource='display_time_s (20 FPS playback, not acquisition timestamps)')
 (OUT/f'{record["id"]}.json').write_text(json.dumps(record,separators=(',',':'),allow_nan=False)+'\n')
 manifest.append({k:record[k] for k in ['id','label','group','action','sensorCount','source','dataKind']}|{'url':f'/action-library/{record["id"]}.json','frames':len(rows)})
 provenance.append({'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'frames':len(rows)})
combined=next(source.glob('*combined.csv'));assert list(csv.DictReader(combined.open(encoding='utf-8-sig')))==parts
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(source/'manifest.json').write_text(json.dumps({'actions':provenance,'combinedIsDuplicate':True,'combinedOrder':['RB004','RB003','RB001']},indent=2)+'\n')
print('Exported 3 contact-voltage clips (938 playback frames); combined CSV verified, not duplicated in catalog.')
