import json
from pathlib import Path
import numpy as np
root=Path(__file__).parent
curves=json.loads((root/'curves.json').read_text())
# Solve crossing parity jointly: both families must alternate, with opposite heights.
occ={}
for ci,c in enumerate(curves):
 for k,(_,sensor) in enumerate(c['crossings']):occ.setdefault(sensor,[]).append((ci,k))
signs={0:1}
while len(signs)<len(curves):
 before=len(signs)
 for entries in occ.values():
  assert len(entries)==2
  (a,ka),(b,kb)=entries
  factor=-((-1)**(ka+kb))
  if a in signs:signs[b]=signs[a]*factor
  elif b in signs:signs[a]=signs[b]*factor
 if len(signs)==before:signs[next(i for i in range(len(curves)) if i not in signs)]=1
for entries in occ.values():
 (a,ka),(b,kb)=entries;assert signs[a]*(-1)**ka == -signs[b]*(-1)**kb
vertices=[];faces=[];parts=[];lift=.25;thickness=.2
for ci,c in enumerate(curves):
 p=np.array(c['samples']);x=p[:,0]
 knots=[k[0] for k in c['crossings']];heights=[signs[ci]*lift*(-1)**k for k in range(len(knots))]
 knots=[0]+knots+[27];heights=[-heights[0]]+heights+[-heights[-1]]
 h=np.zeros(len(x))
 for i in range(len(knots)-1):
  mask=(x>=knots[i]-1e-6)&(x<=knots[i+1]+1e-6)
  t=np.clip(((x[mask]-knots[i])/(knots[i+1]-knots[i])-.34)/.32,0,1)
  t=t*t*t*(10+t*(-15+6*t));h[mask]=heights[i]+(heights[i+1]-heights[i])*t
 normal=np.column_stack([np.full(len(x),-.5/27),p[:,1]/np.linalg.norm(p[:,1:],axis=1),p[:,2]/np.linalg.norm(p[:,1:],axis=1)])
 normal/=np.linalg.norm(normal,axis=1)[:,None]
 tangent=np.gradient(p,axis=0);tangent/=np.linalg.norm(tangent,axis=1)[:,None]
 lateral=np.cross(normal,tangent);lateral/=np.linalg.norm(lateral,axis=1)[:,None]
 sections=[]
 # Cross-sections at a common axial station avoid twisting a broad face across
 # opposite weave heights. Angular width compensates for the strand helix angle.
 theta=np.unwrap(np.arctan2(p[:,2],p[:,1]))
 radius=8.5+.5*x/27
 halfangle=.8/(radius*np.maximum(np.abs(tangent[:,0]),.2))
 for side,depth in [(-1,-1),(1,-1),(-1,1),(1,1)]:
  angle=theta+side*halfangle
  rr=radius+h+depth*thickness/2
  sections.append(np.column_stack([x,rr*np.cos(angle),rr*np.sin(angle)]))
 block=np.stack(sections,axis=1).reshape(-1,3)
 offset=len(vertices);vertices.extend(block.tolist());first=len(faces)
 for i in range(300):
  a=offset+i*4;b=a+4
  faces.extend([[a,a+1,b+1,b],[a+2,b+2,b+3,a+3],[a,b,b+2,a+2],[a+1,a+3,b+3,b+1]])
 a=offset;faces.append([a,a+2,a+3,a+1]);a=offset+1200;faces.append([a,a+1,a+3,a+2])
 parts.append([offset,len(vertices),first,len(faces)])
for start,end in [(0,1),(26,27)]:
 offset=len(vertices);first=len(faces)
 for x,h in [(start,-lift-thickness/2),(end,-lift-thickness/2),(start,lift+thickness/2),(end,lift+thickness/2)]:
  r=8.5+.5*x/27+h
  for i in range(256):
   theta=2*np.pi*i/256;vertices.append([x,r*np.cos(theta),r*np.sin(theta)])
 for i in range(256):
  j=(i+1)%256;o=offset;s=256
  faces.extend([[o+i,o+j,o+s+j,o+s+i],[o+2*s+i,o+3*s+i,o+3*s+j,o+2*s+j],[o+i,o+2*s+i,o+2*s+j,o+j],[o+s+i,o+s+j,o+3*s+j,o+3*s+i]])
 parts.append([offset,len(vertices),first,len(faces)])
json.dump({'geometry':{'positions':np.array(vertices).reshape(-1).tolist()},'quads':faces,'parts':parts,'metadata':{'strandCount':len(curves),'crossingCount':len(occ),'illustrationWidth':1.6,'thickness':thickness,'lift':lift}},open(root/'finger-woven-model.json','w'))
print(f'Built {len(curves)} strands; validated opposite alternating parity at {len(occ)} crossings')
