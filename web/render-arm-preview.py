from pathlib import Path
import struct,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
root=Path(__file__).resolve().parent
b=(root/'public/assets/arm-mannequin.glb').read_bytes();size=struct.unpack_from('<I',b,12)[0];g=json.loads(b[20:20+size]);base=28+size
def accessor(i):
 a=g['accessors'][i];v=g['bufferViews'][a['bufferView']];dim=3 if a['type']=='VEC3' else 1
 return np.frombuffer(b,dtype='<f4' if a['componentType']==5126 else '<u4',count=a['count']*dim,offset=base+v.get('byteOffset',0)).reshape(-1,dim)
v=accessor(0);indices=accessor(2).reshape(-1,3);normals=accessor(1)[indices].mean(1)
p=json.loads((root/'public/assets/model.json').read_text());sp=np.array(p['geometry']['positions']).reshape(-1,3);si=np.array(p['geometry']['indices']).reshape(-1,3)
faces=np.concatenate([v[indices],sp[si]])
sn=np.array(p['geometry']['normals']).reshape(-1,3)[si].mean(1)
ns=np.concatenate([normals,sn]);light=np.array([-.4,-.6,1]);light/=np.linalg.norm(light)
shade=.45+.55*np.abs(ns@light)
colors=np.concatenate([np.tile([.93,.92,.90],(len(indices),1)),np.array(p['geometry']['colors']).reshape(-1,3)[si].mean(1)])*shade[:,None]
fig=plt.figure(figsize=(12,10),facecolor='#111722');ax=fig.add_subplot(111,projection='3d',facecolor='#111722')
ax.add_collection3d(Poly3DCollection(faces,facecolors=np.clip(colors,0,1),edgecolors='none',rasterized=True))
ax.set_xlim(-280,330);ax.set_ylim(-130,130);ax.set_zlim(-220,220);ax.set_box_aspect([610,260,440]);ax.view_init(elev=22,azim=-75);ax.set_axis_off();fig.subplots_adjust(0,0,1,1)
fig.savefig(root.parent/'arm-wearing-preview.png',dpi=130,facecolor=fig.get_facecolor(),bbox_inches='tight',pad_inches=0)
