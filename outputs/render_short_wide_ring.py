"""Render smooth ribbon illustrations with per-pixel depth and clean visible contours."""
import runpy, sys, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
root=Path(__file__).resolve().parent
for kind,script in [('finger',root/'finger-weave/render_styled_svg.py')]:
 sys.argv=[str(script),'--flat','--smooth']
 d=runpy.run_path(str(script))
 # Shorter/wider ring: retain physical strip width and surface spacing.
 old=d['v'][:20*301*4].reshape(20,301,4,3)
 length=20.25;diameter_scale=1.2
 x=np.linspace(0,length,301);source_x=x+(27-length)/2
 strips=[]
 for family in range(2):
  template=old[family*10]
  center=template.mean(axis=1)
  center_angle=np.unwrap(np.arctan2(center[:,2],center[:,1]))
  center_angle=np.interp(source_x,center[:,0],center_angle)/diameter_scale
  pitch=2*np.pi/12
  # Endpoints on the same angular lattice guarantee one partner per strand.
  span=round((center_angle[-1]-center_angle[0])/pitch)*pitch
  u=x/length
  correction=-center_angle[0]+u*(span-(center_angle[-1]-center_angle[0]))
  for k in range(12):
   edges=[]
   for edge in range(4):
    q=template[:,edge];theta=np.unwrap(np.arctan2(q[:,2],q[:,1]))
    theta=np.interp(source_x,q[:,0],theta)/diameter_scale+correction+2*np.pi*k/12
    # Retain the smooth width profile while making both ends symmetric.
    edge_offset=theta-(center_angle+correction+2*np.pi*k/12)
    sign=-1 if edge in (0,2) else 1
    width=np.abs(edge_offset)
    theta=center_angle+correction+2*np.pi*k/12+sign*width
    radius=(8.5+.5*source_x/27)*diameter_scale
    edges.append(np.column_stack((x,radius*np.cos(theta),radius*np.sin(theta))))
   strips.append(np.stack(edges,axis=1))
 # Verify all 12 crossings at each end have exactly two coincident centerlines.
 centers=np.array(strips).mean(axis=2)
 for end in [0,-1]:
  a=centers[:12,end];b=centers[12:,end]
  distances=np.linalg.norm(a[:,None]-b[None,:],axis=2)
  assert len(set(distances.argmin(1)))==12
  assert distances.min(1).max()<.02, distances.min(1).max()
 print('Validated 12 paired, closed crossings at each end.')
 bands=[]
 for start,end in [(0,1),(length-1,length)]:
  for station,offset in [(start,-.35),(end,-.35),(start,.35),(end,.35)]:
   theta=np.arange(256)*2*np.pi/256
   radius=(8.5+.5*(station+(27-length)/2)/27)*diameter_scale+offset
   bands.extend(np.column_stack((np.full(256,station),radius*np.cos(theta),radius*np.sin(theta))))
 v=np.concatenate((np.array(strips).reshape(-1,3),np.array(bands)))
 depth=v.copy()
 # Depth offsets create clean alternating crossings without visible thickness.
 for k in range(24):
  q=depth[k*301*4:(k+1)*301*4]
  theta=np.unwrap(np.arctan2(q.reshape(301,4,3).mean(1)[:,2],q.reshape(301,4,3).mean(1)[:,1]))
  h=.3*np.cos(12*theta)*(1 if k<12 else -1)
  q[:,1:]+=q[:,1:]/np.linalg.norm(q[:,1:],axis=1)[:,None]*np.repeat(h,4)[:,None]
 view=d['view'];p=np.column_stack((v@d['right'],-v@d['up'],depth@view))
 W=800;H=800;scale=min((H-170)/np.ptp(p[:,1]),(W-130)/np.ptp(p[:,0]));p*=scale
 p[:,0]+=(W-p[:,0].max()-p[:,0].min())/2;p[:,1]+=(H-p[:,1].max()-p[:,1].min())/2
 d.update(p=p,v=v,W=W,H=H)
 if kind=='arm':
  # Actual original mesh surfaces, without fitted or extended trajectories.
  v=d['v'].copy()
  v[:24*751*4]=np.array(json.loads((root/'arm-weave/original-flat-ribbons.json').read_text())['positions'])
  depth=v.copy()
  knots=np.array([0,31.64,53.18,70.89,87.82,106.44,130.35,167.86,250])
  for strand in range(24):
   q=depth[strand*751*4:(strand+1)*751*4]
   x=q[:,0];i=np.clip(np.searchsorted(knots,x)-1,0,len(knots)-2)
   t=np.clip((x-knots[i])/(knots[i+1]-knots[i]),0,1)
   t=np.clip((t-.24)/.52,0,1);t=t*t*(3-2*t)
   h=.8*(1 if strand<12 else -1)*(-1.)**i*(1-2*t)
   radial=q[:,1:]/np.linalg.norm(q[:,1:],axis=1)[:,None]
   q[:,1:]+=radial*h[:,None]
  view=d['view'];right=d['right'];up=d['up']
  p=np.column_stack((v@right,-v@up,depth@view))
  W,H=d['W'],d['H'];scale=min((H-170)/np.ptp(p[:,1]),(W-130)/np.ptp(p[:,0]));p*=scale
  p[:,0]+=(W-p[:,0].max()-p[:,0].min())/2;p[:,1]+=(H-p[:,1].max()-p[:,1].min())/2
  d['p']=p;d['v']=v
 p=d['p'].copy();v=d['v'];W,H=d['W'],d['H'];S=8
 p[:,:2]*=S
 zbuf=np.full((H*S,W*S),-np.inf,dtype=np.float32)
 pixels=np.zeros((H*S,W*S,4),dtype=np.uint8)
 def face(ids,color,depth_bias=0):
  for ix in [(0,1,2),(0,2,3)]:
   q=p[np.array(ids)[list(ix)]];a,b,c=q
   lo=np.maximum(np.floor(q[:,:2].min(0)).astype(int),0);hi=np.minimum(np.ceil(q[:,:2].max(0)).astype(int),[W*S-1,H*S-1])
   x0,y0=lo;x1,y1=hi
   den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
   if abs(den)<1e-9:continue
   yy,xx=np.mgrid[y0:y1+1,x0:x1+1]
   u=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
   w=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den
   z=u*a[2]+w*b[2]+(1-u-w)*c[2]+depth_bias
   buf=zbuf[y0:y1+1,x0:x1+1]
   mask=(u>=-1e-7)&(w>=-1e-7)&(u+w<=1.0000001)&(z>=buf)
   buf[mask]=z[mask];pixels[y0:y1+1,x0:x1+1][mask]=[*color,255]
 count,stations,start,end=(24,301,0,300) if kind=='finger' else (24,751,0,750)
 for strand in range(count):
  o=strand*stations*4
  for i in range(start,end):
   a=o+i*4;b=a+4;face([a,a+1,b+1,b],[252,253,252])
 for band in range(2):
  o=count*stations*4+band*1024;s=256
  for i in range(s):
   j=(i+1)%s
   for ids in [[o+i,o+j,o+s+j,o+s+i],[o+2*s+i,o+3*s+i,o+3*s+j,o+2*s+j],[o+i,o+2*s+i,o+2*s+j,o+j],[o+s+i,o+s+j,o+3*s+j,o+3*s+i]]:face(ids,[69,97,107],depth_bias=3.0)
 im=Image.fromarray(pixels.copy());draw=ImageDraw.Draw(im)
 runs=0
 for strand in range(count):
  base=np.array([48,108,123] if strand<count//2 else [49,111,94]);o=strand*stations*4
  for edge in [0,1]:
   samples=[];colors=[]
   for i in range(start,end):
    a=o+i*4+edge;b=a+4;A,B=p[a],p[b]
    n=max(2,int(np.linalg.norm(B[:2]-A[:2])*2)+1)
    t=np.linspace(0,1,n,endpoint=False)
    samples.extend(A[None,:]+t[:,None]*(B-A))
    mid=v[a];rad=np.array([0,mid[1],mid[2]]);rad/=np.linalg.norm(rad)
    mix=np.clip((rad@d['view']+.15)/.45,0,1)
    colors.extend([tuple(np.rint(np.array([157,179,189])*(1-mix)+base*mix).astype(int))]*n)
   q=np.array(samples);xy=np.rint(q[:,:2]).astype(int)
   # Sample adjacent pixels at the exact boundary to avoid raster-rounding gaps.
   dep=np.stack([zbuf[np.clip(xy[:,1]+dy,0,H*S-1),np.clip(xy[:,0]+dx,0,W*S-1)] for dx,dy in [(0,0),(1,0),(-1,0),(0,1),(0,-1)]])
   visible=q[:,2]>=np.min(dep,axis=0)-.035
   starts=np.flatnonzero(visible & ~np.r_[False,visible[:-1]])
   ends=np.flatnonzero(visible & ~np.r_[visible[1:],False])
   for a,b in zip(starts,ends):
    # Discard tiny exposed slivers: they read as stray dots, not useful contours.
    if np.linalg.norm(q[b,:2]-q[a,:2])<3*S:continue
    draw.line([tuple(x) for x in q[a:b+1,:2]],fill=(*colors[(a+b)//2],255),width=round(.8*S),joint='curve');runs+=1
 # Keep contour strokes from bleeding across the solid blue cuff faces.
 band_mask=np.all(pixels[:,:,:3]==[69,97,107],axis=2)&(pixels[:,:,3]==255)
 rendered=np.array(im);rendered[band_mask]=pixels[band_mask];im=Image.fromarray(rendered)
 out=script.parent/'ring-short-wide-closed-clean-transparent.png'
 im.resize((W*6,H*6),Image.Resampling.LANCZOS).save(out, dpi=(300,300))
 # White composite is only for inspection; delivered PNG retains its alpha channel.
 bg=Image.new('RGBA',im.size,'white');bg.alpha_composite(im)
 bg.convert('RGB').resize((W,H),Image.Resampling.LANCZOS).save(script.parent/'ring-short-wide-closed-clean-check.png')
 print(out, 'clean contour runs:',runs,flush=True)
