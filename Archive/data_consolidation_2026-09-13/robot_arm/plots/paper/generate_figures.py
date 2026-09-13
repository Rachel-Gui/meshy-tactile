"""Reproducible paper figures from all 13 measured 132-node scans."""
from pathlib import Path
import json,hashlib
import numpy as np
import openpyxl
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.titlesize':9,'axes.labelsize':8,'xtick.labelsize':7,'ytick.labelsize':7,'svg.fonttype':'none','savefig.facecolor':'white'})
cmap=plt.get_cmap('viridis');norm=Normalize(0,1)
clips=[];provenance=[]
for p in sorted((ROOT/'robot_arm/action_library/robot_arm_132node/segments').glob('*.xlsx')):
 w=openpyxl.load_workbook(p,read_only=True,data_only=True)
 sheets={s.title:list(s.values) for s in w};w.close()
 rows=sheets['Signal Reconstructed'];header=list(rows[0]);mapping=[dict(zip(sheets['Mapping'][0],r)) for r in sheets['Mapping'][1:]]
 assert len(mapping)==132 and len({(int(m['display_row']),int(m['display_column'])) for m in mapping})==132
 a=np.full((len(rows)-1,11,12),np.nan)
 for m in mapping:
  col=header.index(m['node']);assert col+1==int(m['segment_data_column'])
  a[:,int(m['display_row'])-1,int(m['display_column'])-1]=[r[col] for r in rows[1:]]
 assert np.isfinite(a).all() and a.min()>=0 and a.max()<=1
 delta=np.array([r[5:] for r in sheets['Delta Recorded'][1:]],float)
 signal=np.array([r[5:] for r in rows[1:]],float)
 assert np.allclose(signal,np.clip(np.maximum(-delta-.03,0)/.20,0,1),atol=1e-5)
 assert np.count_nonzero(np.array([r[5:] for r in sheets['Signal Recorded'][1:]],float))==0
 meta=dict(sheets['Metadata']);k=int(a.sum((1,2)).argmax())
 d={'id':meta['action_id'],'action':meta['action_type'],'a':a,'peak':k,'times':np.array([r[1] for r in rows[1:]]),'frames':[r[3] for r in rows[1:]],'mapping':mapping}
 clips.append(d);provenance.append({'clip':d['id'],'source':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source_frames':d['frames'],'source_times_s':d['times'].tolist(),'peak_source_frame':d['frames'][k],'peak_source_time_s':float(d['times'][k]),'confidence':meta['confidence']})

def heat(ax,a,title,labels=True):
 im=ax.imshow(a,cmap=cmap,norm=norm,interpolation='nearest',origin='upper',extent=(.5,12.5,11.5,.5),aspect='equal')
 ax.set_xticks(range(1,13));ax.set_yticks(range(1,12));ax.set_title(title,pad=7)
 ax.tick_params(length=2,width=.5)
 for spine in ax.spines.values():spine.set_linewidth(.5)
 if labels:ax.set_xlabel('Display column');ax.set_ylabel('Position after bottom pair')
 return im

def label(d):return d['action'].replace('_',' ').capitalize()+(' (provisional)' if d['id']!='R003' else '')
def save(fig,name):
 fig.savefig(OUT/(name+'.png'),dpi=600,bbox_inches='tight',pad_inches=.05)
 fig.savefig(OUT/(name+'.svg'),bbox_inches='tight',pad_inches=.05)
 plt.close(fig)

fig,axs=plt.subplots(1,3,figsize=(7.2,2.65),layout='constrained')
for i,(ax,d) in enumerate(zip(axs,clips)):
 k=d['peak'];im=heat(ax,d['a'][k],f"({chr(97+i)}) {label(d)}\n{d['id']} · frame {d['frames'][k]} · {d['times'][k]:.2f} s")
fig.colorbar(im,ax=axs,shrink=.78,pad=.025,label='Reconstructed signal (a.u.)',ticks=[0,.25,.5,.75,1])
save(fig,'fig01_contact_comparison_2d')
for d in clips:
 k=d['peak']
 fig,ax=plt.subplots(figsize=(3.6,3.1),layout='constrained')
 im=heat(ax,d['a'][k],f"{label(d)} / {d['id']}\nFrame {d['frames'][k]} · source time {d['times'][k]:.2f} s")
 fig.colorbar(im,ax=ax,shrink=.82,pad=.03,label='Reconstructed signal (a.u.)');save(fig,d['id']+'_peak_2d')
 n=len(d['a']);fig,axs=plt.subplots(1,n,figsize=(7.2,2.6 if n==3 else 2.05),layout='constrained')
 for i,ax in enumerate(axs):
  im=heat(ax,d['a'][i],f"Frame {d['frames'][i]}\n{d['times'][i]:.2f} s",labels=False)
  ax.set_xticks([1,6,12]);ax.set_yticks([1,6,11]);ax.set_xlabel('Display column')
 axs[0].set_ylabel('Position after bottom pair');fig.suptitle(f"{d['id']} · {label(d)} · all measured scans",fontsize=10)
 fig.colorbar(im,ax=axs,shrink=.72,pad=.02,label='Reconstructed signal (a.u.)',ticks=[0,.5,1]);save(fig,d['id']+'_all_scans_2d')
(OUT/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
(OUT/'captions.md').write_text('''# Robot-arm figure captions and methods

**Figure 1. Spatial distribution of reconstructed tactile response on a 132-node robot-arm sensor.** (a) Provisional back touch, R001; (b) provisional front touch, R002; (c) grasp, R003. Each panel shows the measured scan with the greatest sum of reconstructed signals within its clip. All panels use the same 0–1 color scale. Individual cells represent measured nodes in the workbook Mapping layout (11 positions × 12 display columns); no spatial or temporal interpolation is applied. Times refer to the source recording, and frame numbers are the original source frame identifiers. These are selected scans from one session, not averages across trials.

**Temporal panels.** Each R001/R002/R003 all-scans figure includes every measured scan, in chronological order, using the same 0–1 color scale. Full-array scans take approximately 2.64 s; timestamps do not imply simultaneous acquisition of all 132 nodes. R001 has no clean release tail; R002 includes a broad transition/ghost response. Front/back labels remain provisional until mounting orientation is confirmed.

**Signal processing.** Pressure-associated voltage drop = max(−Delta Recorded − 0.03 V, 0); reconstructed signal = clip(voltage drop / 0.20 V, 0, 1). The recorded Signal Recorded values were all zero. The displayed values are reconstructed dimensionless signal, not calibrated pressure or force. Values at 1 are clipped. Raw voltages and recorder delta are preserved in the source XLSX files. The reconstruction formula, 132 unique mapped cells, finite values and complete frame counts are checked by the figure script.

**Column mapping.** Display columns 1–12 correspond to COL ribbons [1,10,12,6,2,3,7,11,5,8,9,4]. Rows are successive positions after the excluded bottom pair; they are not uniform physical distances. Mapping sheets are authoritative.

**Outputs.** PNG at 600 dpi and editable vector SVG. Designed at 7.2-inch comparison/sequence width and 3.6-inch individual-panel width. Source hashes and exact selected frames are in provenance.json.
''')
print(json.dumps(provenance,indent=2))
