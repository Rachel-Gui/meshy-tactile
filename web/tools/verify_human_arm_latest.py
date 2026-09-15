"""Compare every exported Human arm value and scene boundary to the source CSV."""
import csv,json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=root/'web/public/action-library'
manifest=json.loads((out/'manifest.json').read_text());entries=[x for x in manifest if x['sensorCount']==96]
assert len(entries)==10 and all(x['id'].startswith('latest_human_arm_') for x in entries)
source=root/entries[0]['source'];rows=list(csv.DictReader(source.open()));expected=[[float(r[f'N{i:03}']) for i in range(1,97)] for r in rows]
all_clip=json.loads((out/(entries[0]['id']+'.json')).read_text())
assert all_clip['signal']==expected
assert all_clip['times']==[float(r['source_elapsed_s']) for r in rows]
assert all_clip['sourceSha256']==hashlib.sha256(source.read_bytes()).hexdigest()
joined=[]
for entry in entries[1:]:
 c=json.loads((out/(entry['id']+'.json')).read_text());a,b=c['sourceRowRange'];part=rows[a-2:b-1]
 assert c['signal']==expected[a-2:b-1]
 assert len({r['action_label'] for r in part})==1
 assert c['sourceFrames']==[r['source_frame'] for r in part]
 assert c['rotationRows']==[r['rotation_rows'] for r in part]
 assert c['times']==[round(float(r['source_elapsed_s'])-float(part[0]['source_elapsed_s']),6) for r in part]
 joined+=c['signal']
assert joined==expected
print(f'PASS: all {len(rows)*96:,} values, 9 complete scenes, source checksum, frame metadata and timing match CSV exactly.')
