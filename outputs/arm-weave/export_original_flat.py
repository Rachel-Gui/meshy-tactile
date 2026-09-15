"""Read original Rhino strip surfaces; preserve their trajectories and widths."""
import json
from pathlib import Path
import numpy as np
import rhino3dm
root=Path(__file__).resolve().parents[2]
m=rhino3dm.File3dm.Read(str(root/'models/tactile/human_arm.3dm'))
mesh=next(o.Geometry for o in m.Objects if isinstance(o.Geometry,rhino3dm.Mesh))
v=np.array([[x.X,x.Y,x.Z] for x in mesh.Vertices]);parent=list(range(len(v)))
def find(i):
 while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
 return i
for f in mesh.Faces:
 for j in f:parent[find(j)]=find(f[0])
g={}
for i in range(len(v)):g.setdefault(find(i),[]).append(i)
parts=list(g.values());assert len(parts)==26
ribbons=[]
for ids in parts[:24]:
 first=next(f for f in mesh.Faces if f[0] in ids)
 stations=max(first)-min(first)-1
 q=v[ids].reshape(-1,stations,3)
 t=np.linspace(0,1,q.shape[1]);u=np.linspace(0,1,751)
 edges=[np.column_stack([np.interp(u,t,e[:,k]) for k in range(3)]) for e in [q[0],q[-1]]]
 ribbons.append(np.stack([edges[0],edges[1],edges[0],edges[1]],axis=1))
# Source mesh interleaves the families; group by winding for opposite overlap order.
ribbons.sort(key=lambda q: float(np.unwrap(np.arctan2(q.mean(1)[:,2], q.mean(1)[:,1]))[-1]-np.unwrap(np.arctan2(q.mean(1)[:,2], q.mean(1)[:,1]))[0]) > 0)
# Confirm both original curve families have 12 paired endpoints at each end.
inspection=json.loads((root/'outputs/arm-weave/inspection.json').read_text())
a=next(x['curves'] for x in inspection if x['name']=='RowCurves');b=next(x['curves'] for x in inspection if x['name']=='ColumnCurves')
errors=[]
for end in [0,-1]:
 dist=np.linalg.norm(np.array([x[end] for x in a])[:,None]-np.array([x[end] for x in b])[None,:],axis=2)
 assert len(set(dist.argmin(1)))==12 and dist.min(1).max()<1e-5
 errors.append(float(dist.min(1).max()))
path=root/'outputs/arm-weave/original-flat-ribbons.json'
path.write_text(json.dumps({'positions':np.array(ribbons).reshape(-1,3).tolist(),'source':'models/tactile/human_arm.3dm','endpoint_pair_max_error_mm':errors}))
print('Original model: 24 strip surfaces, 12 paired crossings at each end. Errors:',errors)
