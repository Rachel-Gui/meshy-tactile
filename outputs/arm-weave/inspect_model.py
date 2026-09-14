import json, os
import Rhino
Rhino.RhinoApp.RunScript('_Grasshopper',False)
from Grasshopper.Kernel import GH_DocumentIO
root='/Users/a0000/Desktop/tactile'
io=GH_DocumentIO(); assert io.Open(root+'/models/tactile/1.gh'); d=io.Document
d.Enabled=True; d.NewSolution(False)
c=next(o for o in d.Objects if o.NickName.strip()=='Sensor Heatmap')
ok,source=c.TryGetSource();assert ok
open(root+'/outputs/arm-weave/original_component.py','w').write(source)
def vals(p):return [getattr(x,'Value',x) for x in p.VolatileData.AllData(True)]
report=[]
for p in c.Params.Input:
 vs=vals(p); row={'name':p.Name,'count':len(vs),'types':list(set(type(v).__name__ for v in vs))}
 if p.Name in ['RowCurves','ColumnCurves']:
  row['curves']=[[[v.PointAt(v.Domain.ParameterAt(t)).X,v.PointAt(v.Domain.ParameterAt(t)).Y,v.PointAt(v.Domain.ParameterAt(t)).Z] for t in [0,.25,.5,.75,1]] for v in vs]
 report.append(row)
json.dump(report,open(root+'/outputs/arm-weave/inspection.json','w'),indent=2)
print('Inspected source and inputs')
