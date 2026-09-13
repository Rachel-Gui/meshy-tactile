"""Run in Rhino through rhinocode; derive a new GH definition and bake/export it."""
import os,json,traceback,hashlib,math
import System,Rhino
import Rhino.Geometry as rg
from System.Drawing import PointF
from Grasshopper import Instances
from Grasshopper.Kernel import GH_DocumentIO,GH_ParamAccess,GH_RuntimeMessageLevel
from Grasshopper.Kernel.Special import GH_NumberSlider
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT=os.path.join(ROOT,'robot_arm','model_validation.json')
def run():
 source=os.path.join(ROOT,'models','tactile','1.gh')
 original_hash=hashlib.sha256(open(source,'rb').read()).hexdigest()
 io=GH_DocumentIO();assert io.Open(source);doc=io.Document
 component=next(o for o in doc.Objects if o.Name=='Python 3 Script')
 sliders={o.NickName:o for o in doc.Objects if o.NickName in ['Length','Radius small','Radius large']}
 width=next(o for o in doc.Objects if o.NickName=='Strip Width' and str(o.CurrentValue)=='4')
 resolution=next(o for o in doc.Objects if str(o.InstanceGuid)=='63309b78-bea8-491d-aa90-39d97eff3446')
 kept=[component,width,resolution]+list(sliders.values())
 for o in list(doc.Objects):
  if o not in kept:doc.RemoveObject(o,False)
 # Keep native sliders and the Rhino Python3 component from the original GH.
 for p in component.Params.Input:p.RemoveAllSources()
 while component.Params.Input.Count>5:component.Params.UnregisterInputParameter(component.Params.Input[component.Params.Input.Count-1],True)
 configs=[('Length',sliders['Length'],250),('FrontRadius',sliders['Radius small'],16),('RearRadius',sliders['Radius large'],16),('StripWidth',width,4),('MeshSize',resolution,1.5)]
 for i,(name,slider,val) in enumerate(configs):
  slider.NickName=name;slider.SetSliderValue(System.Decimal(val));slider.Attributes.Pivot=PointF(100,100+i*65)
  p=component.Params.Input[i];p.Name=name;p.NickName=name;p.Access=GH_ParamAccess.item;p.AddSource(slider)
 band=GH_NumberSlider();band.CreateAttributes();band.NickName='End Band Width (mm)';band.Slider.Minimum=System.Decimal(0.5);band.Slider.Maximum=System.Decimal(50);band.SetSliderValue(System.Decimal(5));band.Attributes.Pivot=PointF(100,425);doc.AddObject(band,False)
 p=System.Activator.CreateInstance(component.Params.Input[1].GetType());p.Name='EndBandWidth';p.NickName='EndBandWidth';p.Access=GH_ParamAccess.item;component.Params.RegisterInputParam(p);p.AddSource(band)
 component.NickName='Robot Arm 132 Heatmap';component.Attributes.Pivot=PointF(450,140)
 component.SetSource(open(os.path.join(ROOT,'robot_arm','robot_arm_gh_component.py')).read())
 component.Params.OnParametersChanged();component.ExpireSolution(False)
 doc.Enabled=True
 # RhinoCode needs its component attached to an active canvas to compile reliably.
 if Instances.ActiveCanvas is not None:Instances.ActiveCanvas.Document=doc
 doc.NewSolution(False)
 errors=[str(t) for o in doc.Objects if hasattr(o,'RuntimeMessages') for t in o.RuntimeMessages(GH_RuntimeMessageLevel.Error)]
 assert not errors,repr(errors)
 def vals(p):return [getattr(x,'Value',x) for x in p.VolatileData.AllData(True)]
 outputs={p.Name:vals(p) for p in component.Params.Output}
 assert outputs.get('HeatMesh'),repr(outputs)
 mesh=next(v for v in outputs['HeatMesh'] if isinstance(v,rg.Mesh));assert mesh.IsValid
 meta=json.loads(str(outputs['Status'][0]));sensors=meta.pop('sensors')
 assert len(sensors)==132 and len(set(s['node'] for s in sensors))==132
 assert abs(meta['length']-250)<1e-8 and meta['frontDiameter']==32 and meta['rearDiameter']==32
 for s in sensors:assert abs(math.hypot(s['position'][1],s['position'][2])-16)<1e-8
 path=os.path.join(ROOT,'models','robot_arm','robot_arm_132_32mm.gh')
 save=GH_DocumentIO();save.Document=doc;assert save.SaveQuiet(path)
 export_src=open(os.path.join(ROOT,'web','export_grasshopper_model.py')).read().split('\ndocument = Instances.ActiveCanvas')[0]
 ns={'__file__':os.path.join(ROOT,'web','export_grasshopper_model.py')};exec(compile(export_src,'mesh_export_helpers','exec'),ns)
 meta.update({'source':'robot_arm_132_32mm.gh','sourceSha256':hashlib.sha256(open(path,'rb').read()).hexdigest(),'vertexCount':mesh.Vertices.Count,'faceCount':mesh.Faces.Count,'mappingStatus':'Workbook ribbon order; physical mounting phase not calibrated'})
 payload={'metadata':meta,'geometry':ns['mesh_payload'](mesh),'sensors':sensors}
 target=os.path.join(ROOT,'web','public','assets','robot-arm-model.json');json.dump(payload,open(target,'w'),separators=(',',':'))
 # Write a standalone Rhino model without modifying the user's current .3dm.
 model=Rhino.FileIO.File3dm();model.Settings.ModelUnitSystem=Rhino.UnitSystem.Millimeters
 from Rhino.DocObjects import ObjectAttributes
 attr=ObjectAttributes();attr.Name='Robot arm / woven heatmap / 250 mm x diameter 32 mm';model.Objects.AddMesh(mesh,attr)
 for x in [0,250]:
  circle=rg.Circle(rg.Plane(rg.Point3d(x,0,0),rg.Vector3d.XAxis),16)
  at=ObjectAttributes();at.Name='End circle diameter 32 mm';model.Objects.AddCurve(circle.ToNurbsCurve(),at)
 for s in sensors:
  at=ObjectAttributes();at.Name=s['node'];at.SetUserString('displayRow',str(s['displayRow']));at.SetUserString('displayColumn',str(s['displayColumn']));model.Objects.AddPoint(rg.Point3d(*s['position']),at)
 rhino_path=os.path.join(ROOT,'models','robot_arm','robot_arm_132_32mm.3dm');assert model.Write(rhino_path,8)
 assert hashlib.sha256(open(source,'rb').read()).hexdigest()==original_hash
 json.dump({'status':'verified','length':250,'frontDiameter':32,'rearDiameter':32,'sensorCount':132,'errors':errors,'gh':path,'rhino':rhino_path,'export':target,'originalHumanArmUnchanged':True},open(REPORT,'w'),indent=2)
 print('Robot arm GH, Rhino and frontend mesh exported.')
try:run()
except:
 open(REPORT+'.error.txt','w').write(traceback.format_exc());raise
