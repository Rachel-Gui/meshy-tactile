"""Export the current nine direct-format actions; source workbooks remain untouched."""
from pathlib import Path
import ast,json,numpy as np
ROOT=Path(__file__).resolve().parents[2]
# Reuse the viewer's XML reader without starting its Tk UI or selecting a GUI backend.
p=ROOT/'tools/viewers/view_all_heatmaps.py';tree=ast.parse(p.read_text())
tree.body=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom,ast.Assign,ast.AnnAssign,ast.FunctionDef)) and not (isinstance(n,(ast.Import,ast.ImportFrom)) and any(x in ast.unparse(n) for x in ['matplotlib','tkinter']))]
ns={'__file__':str(p)};exec(compile(tree,str(p),'exec'),ns)
OUT=ROOT/'web/public/action-library';OUT.mkdir(exist_ok=True);manifest=[]
robot=json.loads((ROOT/'web/public/assets/robot-arm-model.json').read_text())
for category,directory,count,shape in [('finger','18point_6x6_sparse',18,(3,6)),('human_arm','96point_12x8',96,(12,8)),('robot_arm','robot_arm_132node',132,(11,12))]:
 for file in sorted((ROOT/category/'action_library'/directory/'segments').glob('*.xlsx')):
  tables=ns['read_workbook'](file);info={str(r[0]):r[1] for r in tables['Info'] if len(r)>1};rows=tables['Raw Data'][1:];times=np.array([float(r[2]) for r in rows]);times-=times[0]
  assert int(info['node_count'])==count
  # A uniform playback grid includes the release frame; hold the final sample for <50 ms.
  new=np.arange(int(np.ceil(times[-1]/.05))+1)*.05
  layers={}
  for key,sheet in [('signal','Signal Combined'),('raw','Raw Data'),('baseline','Baseline Fixed')]:
   data=np.array([[ns['as_float'](x) for x in r[5:5+count]] for r in tables[sheet][1:]])
   assert data.shape==(len(times),count) and np.isfinite(data).all()
   layers[key]=np.stack([np.interp(new,times,data[:,i]) for i in range(count)],axis=1).round(6).tolist()
  coords=([{'row':(col+slot)%6+1,'column':col+1} for slot in range(3) for col in range(6)] if count==18 else [{'row':i//shape[1]+1,'column':i%shape[1]+1} for i in range(count)])
  ident=f'direct_{category}_{info["action_id"]}'
  record=dict(id=ident,label=f'{info["action_id"]} · {info["action_type"]}',group={'finger':'Finger · 18 nodes · latest','human_arm':'Human arm · 96 nodes · latest','robot_arm':'Robot arm · 132 nodes · latest'}[category],action=info['action_type'],sensorCount=count,source=str(file.relative_to(ROOT)),originalFrames=len(rows),fps=20,interpolated=True,labels=[s['node'] for s in robot['sensors']] if count==132 else tables['Raw Data'][0][5:5+count],sourceLabels=tables['Raw Data'][0][5:5+count],coordinates=coords,times=new.round(6).tolist(),measuredTimes=times.tolist(),sourceFrames=[r[3] for r in rows],signalLayer='Signal Combined',processing=info['combined_signal'],**layers)
  (OUT/f'{ident}.json').write_text(json.dumps(record,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
  manifest.append({k:record[k] for k in ['id','label','group','action','sensorCount','source','originalFrames']}|{'url':f'/action-library/{ident}.json','frames':len(new)})
assert len(manifest)==9
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print('Exported 9 latest direct actions: 3 Finger, 3 Human arm, 3 Robot arm.')
# Include additional voltage-display recordings without re-interpolating them.
import runpy
runpy.run_path(str(ROOT/'web/tools/export_contact_voltage.py'))

runpy.run_path(str(ROOT/'web/tools/export_human_arm_latest.py'), run_name='__main__')

runpy.run_path(str(ROOT/'web/tools/export_delivery.py'), run_name='__main__')
