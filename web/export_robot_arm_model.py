"""Run in Rhino to export the active (or saved) Robot arm Grasshopper model."""
import os,json,hashlib
import Rhino.Geometry as rg
from Grasshopper import Instances
from Grasshopper.Kernel import GH_DocumentIO,GH_RuntimeMessageLevel
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path=os.path.join(ROOT,'models','robot_arm','robot_arm_132_32mm.gh')
doc=Instances.ActiveCanvas.Document if Instances.ActiveCanvas else None
owned=False
if doc is None or not any(o.NickName=='Robot Arm 132 Heatmap' for o in doc.Objects):
 io=GH_DocumentIO();assert io.Open(path);doc=io.Document;owned=True
try:
 doc.Enabled=True;doc.NewSolution(False)
 comp=next(o for o in doc.Objects if o.NickName=='Robot Arm 132 Heatmap')
 errors=[str(t) for t in comp.RuntimeMessages(GH_RuntimeMessageLevel.Error)];assert not errors,repr(errors)
 outputs={p.Name:[getattr(x,'Value',x) for x in p.VolatileData.AllData(True)] for p in comp.Params.Output}
 mesh=next(v for v in outputs['HeatMesh'] if isinstance(v,rg.Mesh));assert mesh.IsValid
 meta=json.loads(str(outputs['Status'][0]));sensors=meta.pop('sensors');assert len(sensors)==132
 saved=GH_DocumentIO();saved.Document=doc;assert saved.SaveQuiet(path)
 helper=open(os.path.join(ROOT,'web','export_grasshopper_model.py')).read().split('\ndocument = Instances.ActiveCanvas')[0]
 ns={'__file__':__file__};exec(compile(helper,'mesh_export_helpers','exec'),ns)
 meta.update({'source':os.path.basename(path),'sourceSha256':hashlib.sha256(open(path,'rb').read()).hexdigest(),'vertexCount':mesh.Vertices.Count,'faceCount':mesh.Faces.Count,'mappingStatus':'Workbook ribbon order; physical mounting phase not calibrated'})
 result={'metadata':meta,'geometry':ns['mesh_payload'](mesh),'sensors':sensors}
 # Local FastAPI serves dist. Update both locations for Reload without a build.
 for directory in ['public','dist']:
  target=os.path.join(ROOT,'web',directory,'assets','robot-arm-model.json')
  if os.path.isdir(os.path.dirname(target)):json.dump(result,open(target,'w'),separators=(',',':'))
 print('Exported Robot arm: %s mm x diameter %s/%s mm, 132 nodes'%(meta['length'],meta['frontDiameter'],meta['rearDiameter']))
finally:
 if owned:doc.Dispose()
