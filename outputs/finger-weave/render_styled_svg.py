"""Vector illustration of the actual woven Arm mesh, matching the reference palette."""
import json, math, argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parent
v=np.array(json.loads((ROOT/'finger-woven-model.json').read_text())['geometry']['positions']).reshape(-1,3)
parser=argparse.ArgumentParser()
parser.add_argument('--view',choices=['original','oblique','reverse','top-oblique','bottom-oblique'],default='original')
args=parser.parse_args()
poses={'original':([.26,-.96,.115],0),'oblique':([.48,-.81,.34],-32),'reverse':([.28,.87,-.40],25),'top-oblique':([.82,-.54,.19],-18),'bottom-oblique':([-.68,-.69,.25],30)}
direction,roll=poses[args.view]
view=np.array(direction);view/=np.linalg.norm(view)
up=np.array([1.,0,0]);right=np.cross(up,view);right/=np.linalg.norm(right);up=np.cross(view,right)
p=np.column_stack((v@right,-v@up,v@view))
angle=math.radians(roll)
x=p[:,0].copy();y=p[:,1].copy()
p[:,0]=x*math.cos(angle)-y*math.sin(angle)
p[:,1]=x*math.sin(angle)+y*math.cos(angle)
W,H=(612,800) if args.view=='original' else (800,800)
scale=min((H-170)/np.ptp(p[:,1]),(W-130)/np.ptp(p[:,0]));p*=scale
p[:,0]+=(W-p[:,0].max()-p[:,0].min())/2
p[:,1]+=(H-p[:,1].max()-p[:,1].min())/2
polys=[]
def hexcolor(a):return '#'+''.join(f'{int(round(x)):02x}' for x in a)
def blend(a,b,t):return np.array(a)*(1-t)+np.array(b)*t

def add(ids,fill,edges=None,stroke=None,width=1):
 q=p[np.array(ids)]
 # Subdivide wide ribbon faces before depth sorting; narrow station strips alone
 # are insufficient when their width spans a crossing.
 nu=max(1,int(np.ceil(max(np.linalg.norm(q[1,:2]-q[0,:2]),np.linalg.norm(q[2,:2]-q[3,:2]))/3)))
 nv=max(1,int(np.ceil(max(np.linalg.norm(q[3,:2]-q[0,:2]),np.linalg.norm(q[2,:2]-q[1,:2]))/3)))
 flags=[]
 for k in range(4):
  flags.append(any(set(e)==set([ids[k],ids[(k+1)%4]]) for e in (edges or [])))
 for i in range(nu):
  for j in range(nv):
   corners=[]
   for u,w in [(i/nu,j/nv),((i+1)/nu,j/nv),((i+1)/nu,(j+1)/nv),(i/nu,(j+1)/nv)]:
    corners.append((1-u)*(1-w)*q[0]+u*(1-w)*q[1]+u*w*q[2]+(1-u)*w*q[3])
   r=np.array(corners);es=[]
   for k,show in enumerate([j==0 and flags[0],i==nu-1 and flags[1],j==nv-1 and flags[2],i==0 and flags[3]]):
    if show:es.append(r[[k,(k+1)%4],:2])
   polys.append((float(r[:,2].mean()),r[:,:2],fill,es,stroke,width))

for strand in range(20):
 offset=strand*1204
 base=[77,138,151] if strand<10 else [80,141,128]
 for i in range(11,289,2):
  a=offset+i*4;b=offset+min(i+2,289)*4
  mid=v[[a,b,a+1,b+1]].mean(0)
  radial=np.array([0,mid[1],mid[2]]);radial/=np.linalg.norm(radial)
  facing=radial@view
  # Back strands are pale; front strands have colored contours and ivory interiors.
  t=np.clip((facing+.15)/.45,0,1)
  edge=hexcolor(blend([197,211,218],base,t))
  side=hexcolor(blend([224,233,236],blend(base,[255,255,255],.25),t))
  fill=hexcolor(blend([255,255,255],[251,253,252],t))
  width=.65+.55*t
  add([a,a+1,b+1,b],fill,[[a,b],[a+1,b+1]],edge,width)
  add([a+2,b+2,b+3,a+3],fill,[[a+2,b+2],[a+3,b+3]],edge,width)
  add([a,b,b+2,a+2],side)
  add([a+1,a+3,b+3,b+1],side)
 for a in [offset+11*4,offset+289*4]:add([a,a+1,a+3,a+2],hexcolor(base))

for band in range(2):
 o=20*1204+band*1024;s=256
 for i in range(s):
  j=(i+1)%s
  mid=v[[o+i,o+j]].mean(0);radial=np.array([0,mid[1],mid[2]]);radial/=np.linalg.norm(radial)
  facing=radial@view
  front=np.clip((facing+.1)/.9,0,1)
  outer=hexcolor(blend([133,153,160],[49,76,86],front))
  inner=hexcolor(blend([148,166,172],[95,120,129],front))
  rim=hexcolor(blend([142,162,169],[64,94,104],front))
  add([o+i,o+j,o+s+j,o+s+i],inner)
  add([o+2*s+i,o+3*s+i,o+3*s+j,o+2*s+j],outer)
  add([o+i,o+2*s+i,o+2*s+j,o+j],rim)
  add([o+s+i,o+s+j,o+3*s+j,o+3*s+i],rim)
polys.sort(key=lambda x:x[0])
svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">','<title>Finger — alternating woven structure</title>','<desc>Vector projection of finger_woven. Blue and green foreground ribbon edges, pale rear ribbons, shaded end rings. Original tapered shape and proportions retained.</desc>',f'<rect id="background" width="{W}" height="{H}" fill="white"/>','<g stroke-linecap="round" stroke-linejoin="round">']
# Render an independent raster preview from exactly the same painter-ordered polygons.
S=3;im=Image.new('RGB',(W*S,H*S),'white');draw=ImageDraw.Draw(im)
for depth,points,fill,edges,stroke,width in polys:
 coords=' '.join(f'{x:.3f},{y:.3f}' for x,y in points)
 svg.append(f'<polygon points="{coords}" fill="{fill}"/>')
 draw.polygon([tuple(q*S) for q in points],fill=fill)
 for e in edges:
  path='M'+' L'.join(f'{x:.3f},{y:.3f}' for x,y in e)
  svg.append(f'<path d="{path}" fill="none" stroke="{stroke}" stroke-width="{width:.2f}"/>')
  draw.line([tuple(q*S) for q in e],fill=stroke,width=max(1,round(width*S)))
svg+=['</g>','</svg>']
out=Path(__file__).parent
stem='finger-front-blue-green'+('' if args.view=='original' else '-'+args.view)
text='\n'.join(svg)
(out/f'{stem}.svg').write_text(text)
(out/f'{stem}-transparent.svg').write_text(text.replace(f'<rect id="background" width="{W}" height="{H}" fill="white"/>',''))
im.resize((W*2,H*2),Image.Resampling.LANCZOS).save(out/f'{stem}-preview.png')
print(f'Exported {len(polys)} vector polygons.')
