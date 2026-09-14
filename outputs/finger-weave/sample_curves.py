import json,traceback
import Rhino
from Grasshopper.Kernel import GH_DocumentIO
OUT='/Users/a0000/Desktop/tactile/outputs/finger-weave'
try:
 io=GH_DocumentIO();assert io.Open('/Users/a0000/Desktop/tactile/models/tactile/ring.gh');d=io.Document;d.Enabled=True;d.NewSolution(False)
 def vals(p):return [getattr(v,'Value',v) for v in p.VolatileData.AllData(True)]
 families=[vals(o.Params.Output[0]) for o in d.Objects if o.Name=='Pull Curve']
 points=vals(next(o for o in d.Objects if o.NickName.strip()=='SensorIntersections'))
 out=[]
 for family,curves in enumerate(families):
  for ci,c in enumerate(curves):
   samples=[]
   for i in range(301):
    x=27.*i/300;lo=c.Domain.T0;hi=c.Domain.T1
    if c.PointAtStart.X>c.PointAtEnd.X:c.Reverse();lo=c.Domain.T0;hi=c.Domain.T1
    for _ in range(28):
     t=(lo+hi)/2
     if c.PointAt(t).X<x:lo=t
     else:hi=t
    p=c.PointAt((lo+hi)/2);samples.append([p.X,p.Y,p.Z])
   crossings=[]
   for index,p in enumerate(points):
    ok,t=c.ClosestPoint(p)
    if ok and c.PointAt(t).DistanceTo(p)<.02:crossings.append([p.X,index])
   out.append({'family':family,'index':ci,'samples':samples,'crossings':sorted(crossings)})
 json.dump(out,open(OUT+'/curves.json','w'))
except:open(OUT+'/error.txt','w').write(traceback.format_exc());raise
