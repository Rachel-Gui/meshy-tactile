"""Run in Rhino: parametric 5-mm Robot arm and 3-mm Finger end bands."""
import os,json,shutil,traceback,math
import System,Rhino
from System.Drawing import PointF
from Grasshopper import Instances
from Grasshopper.Kernel import GH_DocumentIO,GH_ParamAccess,GH_RuntimeMessageLevel
from Grasshopper.Kernel.Special import GH_NumberSlider
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT=os.path.join(ROOT,'Archive','validation_reports','end_bands_robot_finger')
COMMON='''
# ROBOT_FINGER_END_BANDS_V1
import math
if HeatMesh is not None:
    bw = float(EndBandWidth)
    assert 0 < bw < bl / 2
    band_start_vertex = HeatMesh.Vertices.Count
    for start, end in [(0,bw),(bl-bw,bl)]:
        band = rg.Mesh()
        segments = 192
        for x, inset in [(start,0),(end,0),(start,0.2),(end,0.2)]:
            radius = br0+(br1-br0)*x/bl+0.3-inset
            for i in range(segments):
                angle = 2*math.pi*i/segments
                band.Vertices.Add(x,radius*math.cos(angle),radius*math.sin(angle))
        for i in range(segments):
            j=(i+1)%segments
            band.Faces.AddFace(i,j,segments+j,segments+i)
            band.Faces.AddFace(2*segments+i,3*segments+i,3*segments+j,2*segments+j)
            band.Faces.AddFace(i,2*segments+i,2*segments+j,j)
            band.Faces.AddFace(segments+i,segments+j,3*segments+j,3*segments+i)
        band.Normals.ComputeNormals()
        for i in range(band.Vertices.Count):
            BAND_COLOR
        HeatMesh.Append(band)
    HeatMesh.Normals.ComputeNormals()
    HeatMesh.Compact()
    BAND_STATUS
'''
def values(p):return [getattr(v,'Value',v) for v in p.VolatileData.AllData(True)]
def add_input(c,name,source):
 p=System.Activator.CreateInstance(c.Params.Input[1].GetType());p.Name=name;p.NickName=name;p.Access=GH_ParamAccess.item;c.Params.RegisterInputParam(p);p.AddSource(source)
def apply(kind,path,width):
 backup=os.path.join(ROOT,'Archive','model_backups',kind+'.before-end-bands.gh');
 if not os.path.exists(backup):shutil.copy2(path,backup)
 io=GH_DocumentIO();assert io.Open(path);d=io.Document
 c=next(o for o in d.Objects if o.Name=='Python 3 Script');ok,source=c.TryGetSource();assert ok
 if 'ROBOT_FINGER_END_BANDS_V1' in source:return d
 slider=GH_NumberSlider();slider.CreateAttributes();slider.NickName='End Band Width (mm)';slider.Slider.Minimum=System.Decimal(0.5);slider.Slider.Maximum=System.Decimal(10 if kind=='finger' else 50);slider.SetSliderValue(System.Decimal(width));slider.Attributes.Pivot=PointF(c.Attributes.Pivot.X-240,c.Attributes.Pivot.Y+260);d.AddObject(slider,False);add_input(c,'EndBandWidth',slider)
 if kind=='robot_arm':
  prefix='\nbl=float(Length);br0=float(FrontRadius);br1=float(RearRadius)\n'
  color='band.VertexColors.Add(Color.FromArgb(20,30,110))'
  status="band_meta=json.loads(Status);band_meta.update({'endBandWidth':bw,'endBandCount':2,'bandStartVertex':band_start_vertex});Status=json.dumps(band_meta)"
 else:
  named={o.NickName.strip():o for o in d.Objects}
  for name,nick in [('EndBandLength','Length'),('EndBandFrontRadius','Radius small'),('EndBandRearRadius','Radius large')]:add_input(c,name,named[nick])
  prefix='\nbl=float(EndBandLength);br0=float(EndBandFrontRadius);br1=float(EndBandRearRadius)\n'
  color='band.VertexColors.Add(heat_color(calculate_field_value(rg.Point3d(band.Vertices[i]),sensor_points,sensor_values,heat_radius)))'
  status="Status += ' | two %.1f mm end bands' % bw"
 code=source+prefix+COMMON.replace('BAND_COLOR',color).replace('BAND_STATUS',status)
 c.SetSource(code);c.Params.OnParametersChanged();c.ExpireSolution(False);d.Enabled=True;Instances.ActiveCanvas.Document=d;d.NewSolution(False)
 errors=[str(t) for o in d.Objects if hasattr(o,'RuntimeMessages') for t in o.RuntimeMessages(GH_RuntimeMessageLevel.Error)];assert not errors,repr(errors)
 output={p.Name:values(p) for p in c.Params.Output};assert output['HeatMesh'],str(output);mesh=output['HeatMesh'][0];assert mesh.IsValid
 if kind=='robot_arm':
  meta=json.loads(str(output['Status'][0]));assert meta['endBandWidth']==width;pts=[Rhino.Geometry.Point3d(*s['position']) for s in meta['sensors']];expected=132
  open(os.path.join(ROOT,'robot_arm','robot_arm_gh_component.py'),'w').write(code)
 else:
  assert 'two 3.0 mm end bands' in str(output['Status']),str(output['Status']);pts=values(next(o for o in d.Objects if o.NickName.strip()=='SensorIntersections'));expected=30
 assert len(pts)==expected
 saved=GH_DocumentIO();saved.Document=d;assert saved.SaveQuiet(path)
 snapshot=os.path.join(ROOT,'models','robot_arm','robot_arm_132_32mm.3dm') if kind=='robot_arm' else os.path.join(ROOT,'models','tactile','finger_end_bands.3dm')
 if os.path.exists(snapshot):shutil.copy2(snapshot,os.path.join(ROOT,'Archive','model_backups',kind+'.before-end-bands.3dm'))
 model=Rhino.FileIO.File3dm();model.Settings.ModelUnitSystem=Rhino.UnitSystem.Millimeters;model.Objects.AddMesh(mesh)
 for pt in pts:model.Objects.AddPoint(pt)
 assert model.Write(snapshot,8)
 exporter=os.path.join(ROOT,'web','export_robot_arm_model.py' if kind=='robot_arm' else 'export_ring_model.py');ns={'__name__':'band_export','__file__':exporter};exec(compile(open(exporter).read(),exporter,'exec'),ns)
 if kind=='finger':ns['export']()
 json.dump({'model':kind,'widthMm':width,'bandCount':2,'sensorCount':expected,'runtimeErrors':errors,'rhinoSnapshot':snapshot},open(os.path.join(OUT,kind+'-result.json'),'w'),indent=2)
 return d
try:
 os.makedirs(OUT,exist_ok=True)
 robot=apply('robot_arm',os.path.join(ROOT,'models','robot_arm','robot_arm_132_32mm.gh'),5)
 finger=apply('finger',os.path.join(ROOT,'models','tactile','ring.gh'),3)
except:open(os.path.join(OUT,'error.txt'),'w').write(traceback.format_exc());raise
