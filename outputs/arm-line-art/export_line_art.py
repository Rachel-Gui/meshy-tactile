"""Export Arm mesh feature edges with sampled hidden-line removal."""
import json
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--view', choices=['perspective','front','back','left','right','top','bottom'], default='perspective')
parser.add_argument('--model', default=str(root/'web/public/assets/model.json'))
parser.add_argument('--output-dir', default=str(Path(__file__).parent))
args = parser.parse_args()
data = json.loads(Path(args.model).read_text())['geometry']
v = np.array(data['positions']).reshape(-1,3)
f = np.array(data['indices']).reshape(-1,3)
# Weld coincident vertices so triangulation seams do not become drawing lines.
_, inv = np.unique(np.round(v,5),axis=0,return_inverse=True)
edges = {}
n = np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
n /= np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12)
directions = {'perspective':[-.65,-.85,.72], 'front':[-1,0,0], 'back':[1,0,0], 'left':[0,-1,0], 'right':[0,1,0], 'top':[0,0,1], 'bottom':[0,0,-1]}
view = np.array(directions[args.view], dtype=float); view /= np.linalg.norm(view)
up_hint = [0,1,0] if args.view in ('top','bottom') else [0,0,1]
right = np.cross(up_hint,view); right /= np.linalg.norm(right)
up = np.cross(view,right)
p = np.column_stack((v@right,-v@up,v@view))
p[:,:2] -= p[:,:2].min(axis=0)
scale = 1400 / max(np.ptp(p[:,0]),np.ptp(p[:,1]))
p *= scale; p[:,:2] += 70
W,H = np.ceil(p[:,:2].max(axis=0)+70).astype(int)
S=3
zbuf = np.full((H*S,W*S),-np.inf,dtype=np.float32)
for tri in f:
    q=p[tri].copy(); q[:,:2]*=S
    x0,y0=np.maximum(np.floor(q[:,:2].min(axis=0)).astype(int),0)
    x1,y1=np.minimum(np.ceil(q[:,:2].max(axis=0)).astype(int),[W*S-1,H*S-1])
    a,b,c=q
    den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
    if abs(den)<1e-9: continue
    yy,xx=np.mgrid[y0:y1+1,x0:x1+1]
    u=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
    w=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den
    z=u*a[2]+w*b[2]+(1-u-w)*c[2]
    valid=(u>=-1e-5)&(w>=-1e-5)&(u+w<=1.00001)
    buf=zbuf[y0:y1+1,x0:x1+1]; np.maximum(buf,np.where(valid,z,-np.inf),out=buf)
for i,tri in enumerate(f):
    for a,b in zip(tri,np.roll(tri,-1)):
        key=tuple(sorted((int(inv[a]),int(inv[b]))))
        edges.setdefault(key,[]).append((i,a,b))
paths=[]
for items in edges.values():
    i,a,b=items[0]
    feature=len(items)==1
    if len(items)>1:
        j=items[1][0]
        feature=np.dot(n[i],n[j])<np.cos(np.deg2rad(32)) or (n[i]@view)*(n[j]@view)<0
    if not feature: continue
    A,B=p[a],p[b]; length=np.linalg.norm(B[:2]-A[:2])
    count=max(2,int(length*S*1.5)+1)
    t=np.linspace(0,1,count); pts=A[None,:]+t[:,None]*(B-A)[None,:]
    xy=np.rint(pts[:,:2]*S).astype(int)
    # Adjacent depth pixels avoid losing the exact outer boundary to raster rounding.
    depths=[]
    for dx,dy in [(0,0),(1,0),(-1,0),(0,1),(0,-1)]:
        depths.append(zbuf[np.clip(xy[:,1]+dy,0,H*S-1),np.clip(xy[:,0]+dx,0,W*S-1)])
    visible=pts[:,2]>=np.min(depths,axis=0)-.55
    starts=np.flatnonzero(visible & ~np.r_[False,visible[:-1]])
    ends=np.flatnonzero(visible & ~np.r_[visible[1:],False])
    for start,end in zip(starts,ends):
        if np.linalg.norm(pts[end,:2]-pts[start,:2])>.4:
            paths.append((pts[start,:2],pts[end,:2]))
out=Path(args.output_dir)
out.mkdir(parents=True, exist_ok=True)
stem = 'arm-line-art' if args.view == 'perspective' else f'arm-{args.view}'
svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',f'<title>Arm tactile sleeve — {args.view} line art</title>','<desc>Orthographic view of the Arm model, with hidden lines removed. Source: Arm model mesh. Transparent background.</desc>','<g fill="none" stroke="#181818" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">']
for a,b in paths: svg.append(f'<path d="M{a[0]:.3f},{a[1]:.3f} L{b[0]:.3f},{b[1]:.3f}"/>')
svg+=['</g>','</svg>']
(out/f'{stem}.svg').write_text('\n'.join(svg))
im=Image.new('RGB',(W*2,H*2),'white'); draw=ImageDraw.Draw(im)
for a,b in paths: draw.line([tuple(a*2),tuple(b*2)],fill='#181818',width=3)
im.resize((W,H),Image.Resampling.LANCZOS).save(out/f'{stem}-preview.png')
print(f'Exported {len(paths)} vector segments, {W}×{H}')
