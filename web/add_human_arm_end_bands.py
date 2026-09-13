"""Run in Rhino: add a native End Band Width slider and two parametric end cuffs."""
import os,json,traceback,hashlib,shutil,math
import System,Rhino
import Rhino.Geometry as rg
from System.Drawing import PointF
from Grasshopper import Instances
from Grasshopper.Kernel import GH_DocumentIO,GH_ParamAccess,GH_RuntimeMessageLevel
from Grasshopper.Kernel.Special import GH_NumberSlider
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT=os.path.join(ROOT,'human_arm','end_band_validation.json')
CODE='''
# HUMAN_ARM_END_BANDS_V1
import math
if HeatMesh is not None:
    band_width = float(EndBandWidth)
    end_points = []
    for curve in RowCurves:
        cv = getattr(curve, 'Value', curve)
        end_points.extend([cv.PointAtStart, cv.PointAtEnd])
    x0 = min(p.X for p in end_points)
    x1 = max(p.X for p in end_points)
    ra = sum(math.hypot(p.Y,p.Z) for p in end_points if abs(p.X-x0)<0.01) / sum(1 for p in end_points if abs(p.X-x0)<0.01)
    rb = sum(math.hypot(p.Y,p.Z) for p in end_points if abs(p.X-x1)<0.01) / sum(1 for p in end_points if abs(p.X-x1)<0.01)
    assert 0 < band_width < (x1-x0)/2
    for start, end in [(x0,x0+band_width),(x1-band_width,x1)]:
        band = rg.Mesh()
        segments=192
        # Four circular edges form a closed 0.2-mm-thick tapered ribbon.
        for x, inset in [(start,0),(end,0),(start,0.2),(end,0.2)]:
            radius = ra+(rb-ra)*(x-x0)/(x1-x0)+0.3-inset
            for i in range(segments):
                theta=2*math.pi*i/segments
                band.Vertices.Add(x,radius*math.cos(theta),radius*math.sin(theta))
        for i in range(segments):
            j=(i+1)%segments
            band.Faces.AddFace(i,j,segments+j,segments+i)
            band.Faces.AddFace(2*segments+i,3*segments+i,3*segments+j,2*segments+j)
            band.Faces.AddFace(i,2*segments+i,2*segments+j,j)
            band.Faces.AddFace(segments+i,segments+j,3*segments+j,3*segments+i)
        band.Normals.ComputeNormals()
        for vi in range(band.Vertices.Count):
            vertex=rg.Point3d(band.Vertices[vi])
            band.VertexColors.Add(heat_color(calculate_field_value(vertex,sensor_points,sensor_values,heat_radius)))
        HeatMesh.Append(band)
    HeatMesh.Normals.ComputeNormals()
    HeatMesh.Compact()
    Status += ' | two %.1f mm end bands' % band_width
'''
def run():
 path=os.path.join(ROOT,'models','tactile','1.gh')
 backup=os.path.join(ROOT,'Archive','model_backups','human_arm.before-restore-5mm-20260913.gh')
 os.makedirs(os.path.dirname(backup),exist_ok=True)
 assert not os.path.exists(backup),'Backup already exists; do not reapply blindly'
 shutil.copy2(path,backup)
 io=GH_DocumentIO();assert io.Open(path);d=io.Document
 c=next(o for o in d.Objects if o.NickName.strip()=='Sensor Heatmap')
 ok,source=c.TryGetSource();assert ok and 'HUMAN_ARM_END_BANDS_V1' not in source
 param=System.Activator.CreateInstance(c.Params.Input[1].GetType())
 param.Name='EndBandWidth';param.NickName='EndBandWidth';param.Description='Axial width of both end bands (mm)';param.Access=GH_ParamAccess.item
 c.Params.RegisterInputParam(param)
 slider=GH_NumberSlider();slider.CreateAttributes();slider.NickName='End Band Width (mm)';slider.Slider.Minimum=System.Decimal(1);slider.Slider.Maximum=System.Decimal(50);slider.SetSliderValue(System.Decimal(5));slider.Attributes.Pivot=PointF(c.Attributes.Pivot.X-250,c.Attributes.Pivot.Y+300);d.AddObject(slider,False);param.AddSource(slider)
 c.Params.OnParametersChanged();c.SetSource(source+'\n'+CODE);c.ExpireSolution(False);d.Enabled=True
 Instances.ActiveCanvas.Document=d;d.NewSolution(False)
 def vals(p):return [getattr(x,'Value',x) for x in p.VolatileData.AllData(True)]
 errors=[str(t) for o in d.Objects if hasattr(o,'RuntimeMessages') for t in o.RuntimeMessages(GH_RuntimeMessageLevel.Error)];assert not errors,repr(errors)
 named={o.NickName.strip():o for o in d.Objects}
 meshes=vals(named['HeatmapMesh']);assert meshes and all(m.IsValid for m in meshes)
 sensors=vals(named['SensorIntersections']);assert len(sensors)==96
 output={p.Name:vals(p) for p in c.Params.Output};assert 'two 5.0 mm end bands' in str(output['Status'])
 save=GH_DocumentIO();save.Document=d;assert save.SaveQuiet(path)
 exporter=os.path.join(ROOT,'web','export_grasshopper_model.py');ns={'__name__':'human_export','__file__':exporter};exec(compile(open(exporter).read(),exporter,'exec'),ns)
 asset=os.path.join(ROOT,'web','public','assets','model.json');payload=json.load(open(asset));payload['metadata']['endBandWidth']=5;payload['metadata']['endBandCount']=2
 json.dump(payload,open(asset,'w'),separators=(',',':'))
 shutil.copy2(asset,os.path.join(ROOT,'web','dist','assets','model.json'))
 # Standalone snapshot containing the actual GH mesh and its 96 nodes.
 file=Rhino.FileIO.File3dm();file.Settings.ModelUnitSystem=Rhino.UnitSystem.Millimeters
 for mesh in meshes:file.Objects.AddMesh(mesh)
 for point in sensors:file.Objects.AddPoint(point)
 snapshot=os.path.join(ROOT,'models','tactile','human_arm_end_bands.3dm');assert file.Write(snapshot,8)
 json.dump({'endBandWidthMm':5,'endBandCount':2,'sensorCount':96,'bandIntervalsMm':[[0,5],[245,250]],'errors':errors,'backup':backup,'rhinoSnapshot':snapshot},open(REPORT,'w'),indent=2)
 print('Added two 5 mm end bands, exported Human arm.')
try:run()
except:open(REPORT+'.error.txt','w').write(traceback.format_exc());raise
