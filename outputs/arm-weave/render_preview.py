from pathlib import Path
import json
import numpy as np
from PIL import Image
root=Path(__file__).parent
p=json.loads((root/'arm-woven-model.json').read_text())
v=np.array(p['geometry']['positions']).reshape(-1,3); f=np.array(p['geometry']['indices']).reshape(-1,3)
view=np.array([-.65,-.85,.72]);view/=np.linalg.norm(view)
right=np.cross([0,0,1],view);right/=np.linalg.norm(right);up=np.cross(view,right)
v2=np.column_stack([v@right,-v@up,v@view]);v2[:,:2]-=v2[:,:2].min(0)
v2*=2000/max(np.ptp(v2[:,0]),np.ptp(v2[:,1]));v2[:,:2]+=80
W,H=np.ceil(v2[:,:2].max(0)+80).astype(int)
zbuffer=np.full((H,W),-np.inf);canvas=np.full((H,W,3),249,dtype=np.uint8)
n=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]);n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12)
light=np.array([-.3,-.6,1]);light/=np.linalg.norm(light)
for i,tri in enumerate(f):
 q=v2[tri];a,b,c=q
 den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
 if abs(den)<1e-10:continue
 x0,y0=np.maximum(np.floor(q[:,:2].min(0)).astype(int),0)
 x1,y1=np.minimum(np.ceil(q[:,:2].max(0)).astype(int),[W-1,H-1])
 yy,xx=np.mgrid[y0:y1+1,x0:x1+1]
 u=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
 w=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den
 z=u*a[2]+w*b[2]+(1-u-w)*c[2]
 buf=zbuffer[y0:y1+1,x0:x1+1]
 valid=(u>=0)&(w>=0)&(u+w<=1)&(z>buf)
 # Different colors identify the two curve families, showing alternating occlusion.
 base=np.array([65,134,158] if tri[0]<12*3004 else [219,168,101] if tri[0]<24*3004 else [165,176,181])
 normal=n[i] if n[i]@view>=0 else -n[i]
 color=np.clip(base*(.58+.42*max(0,normal@light)),0,255).astype(np.uint8)
 buf[valid]=z[valid];canvas[y0:y1+1,x0:x1+1][valid]=color
im=Image.fromarray(canvas);im.resize((1620,round(H*1620/W)),Image.Resampling.LANCZOS).save(root/'arm-woven-preview.png')
im.crop((int(W*.20),int(H*.35),int(W*.69),int(H*.83))).save(root/'arm-woven-detail.png')
