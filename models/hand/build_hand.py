"""Reference-inspired hand, millimetres; continuous implicit surface, index axis X."""
from pathlib import Path
import numpy as np,json
from skimage.measure import marching_cubes
R=Path(__file__).resolve().parents[2]
step=.85
origin=np.array([-105.,-78.,-48.]); end=np.array([86.,51.,23.])
x,y,z=np.meshgrid(*[np.arange(a,b+step,step,dtype=np.float32) for a,b in zip(origin,end)],indexing='ij')
f=np.full(x.shape,1000,dtype=np.float32)
def merge(d,k=3):
 global f
 h=np.maximum(k-np.abs(f-d),0)/k
 f=np.minimum(f,d)-h*h*k*.25

def ell(c,r,k=3):
 q=[(v-a)/b for v,a,b in zip([x,y,z],c,r)]
 merge((np.sqrt(sum(v*v for v in q))-1)*min(r),k)
def bone(a,b,ra,rb,k=2):
 a=np.array(a);b=np.array(b);v=b-a
 t=np.clip(((x-a[0])*v[0]+(y-a[1])*v[1]+(z-a[2])*v[2])/sum(v*v),0,1)
 d=np.sqrt((x-a[0]-t*v[0])**2+(y-a[1]-t*v[1])**2+((z-a[2]-t*v[2])/0.88)**2)-(ra+(rb-ra)*t)
 merge(d,k)
# Palm volume and wrist blend, broad knuckles tapering toward wrist.
ell([-37,-25,-1],[34,33,10.5],5)
ell([-60,-25,-2],[25,24,10],5)
bone([-102,-26,-2],[-62,-26,-2],17,20,7)
ell([-37,-1,-3],[23,17,12],5)
# Finger joint centres. Index radius stays inside the existing GH sleeve.
digits=[([[-16,0,0],[27,0,0],[43,1,-6],[55,2,-17]], [7.5,7.1,6.1,5.2]),
([[-12,-18,0],[20,-19,-3],[41,-20,-13],[55,-21,-28]],[8,7.5,6.5,5.5]),
([[-15,-37,-1],[14,-38,-5],[33,-40,-17],[44,-41,-32]],[7.6,7.1,6.1,5.1]),
([[-23,-53,-2],[-1,-55,-6],[14,-57,-18],[21,-58,-31]],[6.4,5.9,5.1,4.4]),
([[-47,2,-2],[-29,19,-3],[-12,27,-10],[0,29,-20]],[10.5,9,7.1,5.7])]
nails=[]
for points,radii in digits:
 for i in range(3):bone(points[i],points[i+1],radii[i],radii[i+1],2.8)
 for point,radius in zip(points[1:3],radii[1:3]):ell(point,[radius*1.12,radius*1.04,radius*.9],1.5)
 a=np.array(points[-2]);b=np.array(points[-1]);c=b*.74+a*.26
 direction=(b-a)/np.linalg.norm(b-a)
 side=np.cross([0.,0.,1.],direction);side/=np.linalg.norm(side)
 normal=np.cross(direction,side)
 center=c+normal*radii[-1]*.79
 nails.append({'center':center.tolist(),'direction':direction.tolist(),'normal':normal.tolist(),'length':float(np.linalg.norm(b-a)*.66),'width':radii[-1]*1.3})
# Flat wrist cut. Closed watertight surface.
f=np.maximum(f,-96-x)
v,faces,n,_=marching_cubes(f,level=0,spacing=(step,)*3,gradient_direction='ascent');v+=origin
# Fit the illustrative index surface to the measured inner radial envelope of
# the unchanged GH sleeve. Keep a small clearance to prevent mesh flicker.
sleeve=json.loads((R/'web/public/assets/ring-model.json').read_text())
sv=np.array(sleeve['geometry']['positions']).reshape(-1,3)
slope=(sleeve['metadata']['rearDiameter']-sleeve['metadata']['frontDiameter'])/(2*sleeve['metadata']['length'])
base=float(np.min(np.linalg.norm(sv[:,1:],axis=1)-slope*sv[:,0]))
clearance=.18
radial=np.linalg.norm(v[:,1:],axis=1)
mask=(v[:,0]>-7)&(v[:,0]<34)&(v[:,1]>-10)&(radial<12)
t=v[mask,0]
blend=np.minimum(np.clip((t+7)/7,0,1),np.clip((34-t)/7,0,1))
blend=blend*blend*(3-2*blend)
target=base+slope*np.clip(t,0,27)-clearance
new_r=radial[mask]*(1-blend)+target*blend
v[mask,1:]*=(new_r/radial[mask])[:,None]
fitmask=mask&(v[:,0]>=0)&(v[:,0]<=27)
fitgap=base+slope*v[fitmask,0]-np.linalg.norm(v[fitmask,1:],axis=1)
assert np.allclose(fitgap,clearance,atol=1e-5)
(R/'models/hand/sleeve-fit.json').write_text(json.dumps({'method':'Illustrative index finger fitted to conservative GH sleeve inner radial envelope','clearanceMm':clearance,'envelopeRadiusAtX0Mm':base,'radiusSlope':slope,'fittedVertices':int(fitmask.sum()),'minClearanceMm':float(fitgap.min()),'maxClearanceMm':float(fitgap.max()),'sleeveGeometryChanged':False},indent=2)+'\n')
out=R/'web/public/assets/hand-model.json'
out.write_text(json.dumps({'positions':v.round(4).ravel().tolist(),'indices':faces.ravel().tolist(),'nails':nails,'metadata':{'units':'mm','description':'Reference-inspired sculpted hand; illustrative, not a scan','indexAxis':'X','wristCutX':-96}},separators=(',',':')))
with (R/'models/hand/hand.obj').open('w') as o:
 o.write('# Reference-inspired continuous hand mesh, mm\n')
 for p in v:o.write('v %.4f %.4f %.4f\n'%tuple(p))
 for p in faces+1:o.write('f %d %d %d\n'%tuple(p))
print(len(v),'vertices',len(faces),'triangles')
