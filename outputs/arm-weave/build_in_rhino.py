import os,json,traceback,hashlib
import System,Rhino
import Rhino.Geometry as rg
from System.Drawing import PointF
from Grasshopper import Instances
from Grasshopper.Kernel import GH_DocumentIO,GH_ParamAccess,GH_RuntimeMessageLevel
from Grasshopper.Kernel.Special import GH_NumberSlider
ROOT='/Users/a0000/Desktop/tactile'
OUT=ROOT+'/outputs/arm-weave'
def run():
 io=GH_DocumentIO();assert io.Open(ROOT+'/models/tactile/1.gh');d=io.Document
 c=next(o for o in d.Objects if o.NickName.strip()=='Sensor Heatmap')
 for idx,(name,value,low,high) in enumerate([('WeaveLift',.8,.1,3),('StripThickness',.4,.1,2),('StripWidth',4,1,8)]):
  param=System.Activator.CreateInstance(c.Params.Input[1].GetType());param.Name=name;param.NickName=name;param.Access=GH_ParamAccess.item
  c.Params.RegisterInputParam(param)
  slider=GH_NumberSlider();slider.CreateAttributes();slider.NickName=name+' (mm)';slider.Slider.DecimalPlaces=2;slider.Slider.Minimum=System.Decimal(low);slider.Slider.Maximum=System.Decimal(high);slider.SetSliderValue(System.Decimal(value));slider.Attributes.Pivot=PointF(c.Attributes.Pivot.X-270,c.Attributes.Pivot.Y+350+idx*50);d.AddObject(slider,False);param.AddSource(slider)
 c.Params.OnParametersChanged()
 source=open(OUT+'/weave_component.py').read()
 c.SetSource(source);c.ExpireSolution(False);d.Enabled=True
 Instances.ActiveCanvas.Document=d;d.NewSolution(False)
 def vals(p):return [getattr(x,'Value',x) for x in p.VolatileData.AllData(True)]
 errors=[str(t) for o in d.Objects if hasattr(o,'RuntimeMessages') for t in o.RuntimeMessages(GH_RuntimeMessageLevel.Error)]
 assert not errors,repr(errors)
 outputs={p.Name:vals(p) for p in c.Params.Output}
 assert outputs.get('HeatMesh'),repr(outputs)
 meshes=outputs['HeatMesh'];assert all(m.IsValid for m in meshes)
 inputs={p.Name:vals(p) for p in c.Params.Input}
 # Evaluate the exact component source to expose individual strand meshes for validation.
 scope={k:(v[0] if len(v)==1 else v) for k,v in inputs.items()};exec(compile(source,'weave_component.py','exec'),scope)
 strands=scope['weave_meshes'][:24]
 crossings=[]
 for i,a in enumerate(strands):
  for j in range(i+1,24):
   lines=rg.Intersect.Intersection.MeshMeshFast(a,strands[j])
   if lines and len(lines): crossings.append({'a':i,'b':j,'segments':len(lines)})
 checks=scope['weave_checks']
 assert all(all(h1*h2<0 for h1,h2 in zip(s['heights'],s['heights'][1:])) for s in checks)
 report={'strandCount':24,'sensorCount':96,'stripWidthMm':4,'stripThicknessMm':.4,'weaveLiftMm':.8,'centerCrossingSurfaceGapMm':1.2,'endBandWidthMm':5,'endBandRadialThicknessMm':2,'closedStrands':all(m.IsClosed for m in strands),'strandIntersections':crossings,'alternation':checks,'errors':errors}
 json.dump(report,open(OUT+'/validation.json','w'),indent=2)
 assert not crossings,'Strands intersect; see validation.json'
 for o in d.Objects:
  if hasattr(o,'Hidden'):o.Hidden=o.NickName.strip() not in ['HeatmapMesh','SensorIntersections']
 path=ROOT+'/models/tactile/human_arm_woven.gh'
 save=GH_DocumentIO();save.Document=d;assert save.SaveQuiet(path)
 file=Rhino.FileIO.File3dm();file.Settings.ModelUnitSystem=Rhino.UnitSystem.Millimeters
 for i,mesh in enumerate(scope['weave_meshes']):
  at=Rhino.DocObjects.ObjectAttributes();at.Name=('Strip_A_%02d'%(i+1) if i<12 else 'Strip_B_%02d'%(i-11) if i<24 else 'End_band_%d'%(i-23))
  file.Objects.AddMesh(mesh,at)
 for p in inputs['Points']:file.Objects.AddPoint(p)
 assert file.Write(ROOT+'/models/tactile/human_arm_woven.3dm',8)
 # Reuse the project's mesh serializer, retaining sensor order and metadata.
 exporter=open(ROOT+'/web/export_grasshopper_model.py').read()
 funcs=exporter[:exporter.index('\ndocument = Instances.')]
 ns={'__file__':ROOT+'/web/export_grasshopper_model.py'};exec(compile(funcs,'serializer','exec'),ns)
 payload=json.load(open(ROOT+'/web/public/assets/model.json'))
 payload['geometry']=ns['mesh_payload'](scope['HeatMesh'])
 payload['metadata'].update({'source':'human_arm_woven.gh','sourceSha256':hashlib.sha256(open(path,'rb').read()).hexdigest(),'vertexCount':scope['HeatMesh'].Vertices.Count,'faceCount':scope['HeatMesh'].Faces.Count,'weave':'alternating plain weave','weaveLift':.8,'stripThickness':.4})
 json.dump(payload,open(OUT+'/arm-woven-model.json','w'),separators=(',',':'))
 # OBJ contains separate named, closed strands, convenient for other 3D editors.
 with open(OUT+'/human_arm_woven.obj','w') as obj:
  obj.write('# Units: mm. Separate closed woven ribbons and end cuffs.\n');offset=1
  for i,m in enumerate(scope['weave_meshes']):
   obj.write('o part_%02d\n'%i)
   for v in m.Vertices:obj.write('v %.7f %.7f %.7f\n'%(v.X,v.Y,v.Z))
   for f in m.Faces:
    ids=[f.A,f.B,f.C]+([f.D] if f.IsQuad else [])
    obj.write('f '+' '.join(str(k+offset) for k in ids)+'\n')
   offset+=m.Vertices.Count
 open(OUT+'/done.txt','w').write('Created woven GH, 3DM, OBJ and JSON; no strand intersections.\n')
try:run()
except:open(OUT+'/error.txt','w').write(traceback.format_exc());raise
