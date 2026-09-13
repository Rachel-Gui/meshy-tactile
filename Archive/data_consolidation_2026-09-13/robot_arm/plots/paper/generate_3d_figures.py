"""Paper views on the exact GH-exported 250 mm × diameter 32 mm frontend mesh."""
from pathlib import Path
import json
import numpy as np
import openpyxl
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
model=json.loads((ROOT/'web/public/assets/robot-arm-model.json').read_text())
v=np.array(model['geometry']['positions']).reshape(-1,3);faces=np.array(model['geometry']['indices']).reshape(-1,3)
sensors=model['sensors'];p=np.array([s['position'] for s in sensors]);size=v.max(0)-v.min(0);center=(v.max(0)+v.min(0))/2
u=np.clip(1-np.linalg.norm(v[:,None,:]-p[None,:,:],axis=2)/10,0,1);weights=u*u*(3-2*u)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'svg.fonttype':'none'})
cmap=plt.get_cmap('viridis');norm=Normalize(0,1)
selected=json.loads((OUT/'provenance.json').read_text());clips=[]
for record in selected:
 w=openpyxl.load_workbook(ROOT/record['source'],read_only=True,data_only=True)
 rows=list(w['Signal Reconstructed'].values);w.close();h=list(rows[0])
 row=next(r for r in rows[1:] if r[h.index('source_frame')]==record['peak_source_frame'])
 values=np.array([row[h.index(s['node'])] for s in sensors],float)
 clips.append((record,values))
def draw(ax,values,azim):
 field=np.max(weights*np.where(values>.001,values,0)[None,:],axis=1)
 ax.add_collection3d(Poly3DCollection(v[faces],facecolors=cmap(field[faces].mean(1)),edgecolors='none'))
 for lim,c,r in zip([ax.set_xlim,ax.set_ylim,ax.set_zlim],center,size):lim(c-r*.54,c+r*.54)
 ax.set_box_aspect(size.copy());ax.view_init(elev=18,azim=azim);ax.set_axis_off()
def save(fig,name):
 for ext in ['png','svg']:fig.savefig(OUT/f'{name}.{ext}',dpi=600,bbox_inches='tight',pad_inches=.05)
 plt.close(fig)
fig=plt.figure(figsize=(7.2,4.3))
for i,(r,a) in enumerate(clips):
 for j,az in enumerate([-75,105]):
  ax=fig.add_axes([.015+i*.30,.49-j*.36,.31,.38],projection='3d');draw(ax,a,az)
  if j==0:ax.set_title(f"{r['clip']} · frame {r['peak_source_frame']}\n{r['peak_source_time_s']:.2f} s",fontsize=8,pad=-6)
fig.text(.02,.94,'Robot arm · 250 mm length · Ø32 mm at both ends',fontsize=10)
fig.text(.02,.065,'Upper/lower rows: opposite views · 132 nodes · 10 mm spatial smoothing',fontsize=8)
fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap=cmap),cax=fig.add_axes([.945,.20,.015,.55]),label='Reconstructed signal (a.u.)')
save(fig,'fig02_robot_arm_3d_comparison')
for r,a in clips:
 fig=plt.figure(figsize=(7.2,2.8))
 for j,az in enumerate([-75,105]):
  ax=fig.add_axes([.01+j*.44,.12,.45,.73],projection='3d');draw(ax,a,az);ax.set_title(['View A','Opposite view'][j],fontsize=8,pad=-7)
 fig.text(.025,.93,f"{r['clip']} · source frame {r['peak_source_frame']} · {r['peak_source_time_s']:.2f} s",fontsize=10)
 fig.text(.025,.04,'250 × Ø32 mm · actual measured scan · workbook node order',fontsize=8)
 fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap=cmap),cax=fig.add_axes([.93,.25,.015,.5]),label='Reconstructed signal (a.u.)');save(fig,r['clip']+'_peak_3d')
print('Saved four 3D figures, each in 600-DPI PNG and SVG.')
