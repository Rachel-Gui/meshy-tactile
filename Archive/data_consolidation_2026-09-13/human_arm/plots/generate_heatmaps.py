"""Render measured Arm clips on the exported 3D mesh; run with Anaconda Python."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
model = json.loads((ROOT/'web/public/assets/model.json').read_text())
v = np.array(model['geometry']['positions']).reshape(-1,3)
f = np.array(model['geometry']['indices']).reshape(-1,3)
sensors = np.array([s['position'] for s in model['sensors']])
sensors = sensors[np.arange(96).reshape(12,8)[:,::-1].ravel()]
d = np.linalg.norm(v[:,None,:]-sensors[None,:,:],axis=2)
u = np.clip(1-d/25,0,1)
weights = u*u*(3-2*u)
cmap = plt.get_cmap('turbo'); norm = Normalize(0,1)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titleweight':'medium'})
lo=v.min(0); hi=v.max(0); center=(lo+hi)/2; size=hi-lo
records=[]
def draw(ax,values,title,azim=-65):
    values=np.clip(values,0,1)
    values=np.where(values>0.001,values,0)
    field=np.max(weights*values[None,:],axis=1)
    colors=cmap(field[f].mean(1))
    ax.add_collection3d(Poly3DCollection(v[f],facecolors=colors,edgecolors='none'))
    for setlim,c,r in zip([ax.set_xlim,ax.set_ylim,ax.set_zlim],center,size):setlim(c-r*.55,c+r*.55)
    ax.set_box_aspect(size.copy());ax.view_init(elev=24,azim=azim);ax.set_axis_off();ax.set_title(title,pad=0,color='#17263c')
    return ax

def save(fig,name):
    fig.savefig(OUT/f'{name}.png',dpi=300,facecolor='white')
    plt.close(fig)

clips=[]
for action in ['grasp','front_touch','back_touch']:
    candidates=[]
    for p in (ROOT/'web/public/action-library').glob('96_segment*.json'):
        data=json.loads(p.read_text())
        if data['action']==action and not data['interpolated']:
            a=np.array(data['signal'],dtype=float)
            if np.isfinite(a).all(): candidates.append((float(a.sum(1).max()),data,a))
    _,data,a=max(candidates,key=lambda item:item[0]); k=int(a.sum(1).argmax())
    clips.append((data,a,k))
    title=action.replace('_',' ').title();time=data['times'][k]
    fig=plt.figure(figsize=(12,5.6))
    fig.suptitle(f'ARM / {title.upper()}',x=.06,ha='left',fontsize=19,weight='bold',y=.96)
    fig.text(.06,.89,f"{data['id'].split('_')[-1]}  ·  frame {k+1}/{len(a)}  ·  t = {time:.2f} s  ·  96 measured channels",color='#526278')
    for i,angle in enumerate([-65,115]):draw(fig.add_subplot(1,2,i+1,projection='3d'),a[k],['View A','Opposite view'][i],angle)
    fig.subplots_adjust(left=.01,right=.89,top=.84,bottom=.13,wspace=-.12)
    fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap=cmap),cax=fig.add_axes([.92,.25,.014,.49]),label='Processed signal (0–1)')
    fig.text(.06,.055,'Peak total signal frame · shared scale · spatial smoothing radius 25 mm · no temporal interpolation',fontsize=9,color='#526278')
    save(fig,action+'_3d_heatmap')
    records.append({'action':action,'clip':data['id'],'source':data['source'],'frame_1_based':k+1,'time_seconds':time,'selection':'Maximum sum of 96 signals; strongest complete non-interpolated clip per action'})
fig=plt.figure(figsize=(15,6))
fig.suptitle('ARM / THREE CONTACT PATTERNS',x=.045,ha='left',fontsize=20,weight='bold',y=.96)
for i,(data,a,k) in enumerate(clips):
    draw(fig.add_subplot(1,3,i+1,projection='3d'),a[k],f"{data['action'].replace('_',' ').title()} / {data['id'].split('_')[-1]}\nt = {data['times'][k]:.2f} s")
fig.subplots_adjust(left=0,right=.92,top=.80,bottom=.15,wspace=-.20)
fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap=cmap),cax=fig.add_axes([.95,.25,.012,.45]),label='Processed signal (0–1)')
fig.text(.045,.065,'Actual 96-channel recordings mapped to the Arm mesh · same viewpoint and scale · peak total signal in each clip',color='#526278')
save(fig,'arm_contact_comparison')
data,a,k=clips[0]
ks=[0,k//2,k,len(a)-1]
fig=plt.figure(figsize=(16,7))
fig.suptitle(f"ARM / GRASP OVER TIME — {data['id'].split('_')[-1]}",x=.04,ha='left',fontsize=20,weight='bold',y=.97)
for i,(idx,label) in enumerate(zip(ks,['Start','Before peak','Peak','End'])):
    ax=fig.add_axes([i*.235,.33,.255,.49],projection='3d');draw(ax,a[idx],f'{label} · {data["times"][idx]:.2f} s')
ax=fig.add_axes([.08,.10,.80,.18]);ax.plot(data['times'],a.sum(1),color='#273f67',lw=1.6)
for idx in ks:ax.scatter(data['times'][idx],a[idx].sum(),color=cmap(.8),s=24,zorder=4)
ax.set_xlabel('Time within clip (s)');ax.set_ylabel('Sum of signal');ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.15)
fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap=cmap),cax=fig.add_axes([.955,.41,.01,.35]),label='Processed signal (0–1)')
save(fig,'grasp_time_sequence')
(OUT/'selection.json').write_text(json.dumps(records,indent=2)+'\n')
(OUT/'README.md').write_text('''# Arm 3D heatmap plots

Five 300-DPI PNGs generated from the existing measured 96-channel action exports and `web/public/assets/model.json`.

- Three per-action images show two opposite views of peak total signal.
- `arm_contact_comparison.png`: common-view comparison.
- `grasp_time_sequence.png`: four measured frames and summed-signal timeline.

Selection uses the strongest peak summed signal among complete, non-temporally-interpolated clips in each action class. Exact sources, frames and timestamps are in `selection.json`. These are representative high-response examples, not class averages.

The frontend channel mapping is preserved: reverse the eight exported sensor coordinates within each of 12 rows. Vertex signal uses the frontend maximum smoothstep influence with a 25 mm radius, gain 1 and threshold 0. Triangle colors average their vertex values. All plots share the 0–1 processed-signal scale (not calibrated force/pressure); spatial interpolation is visual only. The mesh is the current exported Arm geometry. Opposite views reveal contacts hidden on the far surface. No generated or simulated sensor data is used.

Regenerate from project root:

```sh
/Users/a0000/anaconda3/bin/python human_arm/plots/generate_heatmaps.py
```
''')
print(json.dumps(records,indent=2))
print('Saved 5 PNG plots to',OUT)
