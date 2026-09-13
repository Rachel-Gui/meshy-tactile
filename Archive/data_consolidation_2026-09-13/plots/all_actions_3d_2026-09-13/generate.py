"""Measured-frame selection and fixed-camera plots using current frontend meshes."""
from pathlib import Path
import os,json,sys,importlib.util,hashlib,csv,html
os.environ['MPLCONFIGDIR']='/private/tmp/tactile-paper-mpl'
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap,Normalize
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from PIL import Image,ImageOps,ImageDraw
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
spec=importlib.util.spec_from_file_location('viewer',ROOT/'tools/viewers/view_all_heatmaps.py');v=importlib.util.module_from_spec(spec);sys.modules[spec.name]=v;spec.loader.exec_module(v);matplotlib.use("Agg",force=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'svg.fonttype':'none'})
# Interpolate the same thermal stops as Three.js in linear RGB, then return sRGB.
stops=np.array([[20,30,110],[0,170,255],[30,220,120],[255,220,0],[230,30,20]])/255
linear=np.where(stops<=.04045,stops/12.92,((stops+.055)/1.055)**2.4)
x=np.linspace(0,1,256);rgb=np.array([np.interp(x,np.linspace(0,1,5),linear[:,c]) for c in range(3)]).T
rgb=np.where(rgb<=.0031308,12.92*rgb,1.055*rgb**(1/2.4)-.055)
cmap=LinearSegmentedColormap.from_list('frontend_thermal',rgb,N=256)
MODELS={'finger':('ring-model.json',3),'robot_arm':('robot-arm-model.json',10),'human_arm':('model.json',25)}
models={}
for kind,(file,radius) in MODELS.items():
 p=ROOT/'web/public/assets'/file;m=json.loads(p.read_text());verts=np.array(m['geometry']['positions']).reshape(-1,3);faces=np.array(m['geometry']['indices']).reshape(-1,3);sensors=np.array([s['position'] for s in m['sensors']])
 if kind=='finger':mapping=np.array(json.loads((OUT/'finger_mapping.json').read_text()))
 elif kind=='human_arm':mapping=np.arange(96).reshape(12,8)[:,::-1].ravel()
 else:mapping=np.arange(132)
 points=sensors[mapping];dist=np.linalg.norm(verts[:,None,:]-points[None,:,:],axis=2);u=np.clip(1-dist/radius,0,1);weights=u*u*(3-2*u)
 nearest=np.argsort(np.linalg.norm(points[:,None]-points[None,:],axis=2),axis=1,kind='stable')[:,:6]
 models[kind]=dict(m=m,v=verts,f=faces,p=points,w=weights,near=nearest,radius=radius,mapping=mapping,hash=hashlib.sha256(p.read_bytes()).hexdigest())
records=[]
entries=[e for group in v.discover_entries().values() for e in group]
for number,e in enumerate(entries):
 kind='finger' if e.kind in ['30_combined','18_segment'] else 'robot_arm' if e.kind=='132_segment' else 'human_arm';q=models[kind]
 data=v.load_30(e) if e.kind=='30_combined' else v.load_segment(e)
 raw=data['signal'].reshape(len(data['signal']),-1);a=np.clip(np.nan_to_num(raw,nan=0),0,1);assert a.shape[1]==len(q['p']);assert np.nanmin(raw)>=0 and np.nanmax(raw)<=1.00001
 # Densest local region: largest mean response among a sensor and its five
 # spatially nearest measured channels. Tie-break with total signal, then time.
 local=a[:,q['near']].mean(axis=2);scores=local.max(axis=1);idx=max(range(len(a)),key=lambda i:(scores[i],a[i].sum(),-i));hot=int(np.argmax(local[idx]));values=a[idx]
 with v.ZipFile(e.path) as z:
  rows=v.read_sheet(z,{'back_touch':'Back Touch','front_touch':'Front Touch','grasp':'Grasp'}[e.action_type] if e.kind=='30_combined' else 'Raw Data')
  header=rows[0];rows=[r for r in rows[1:] if r and (e.kind!='30_combined' or r[0]==e.action_id)];sf=int(float(rows[idx][header.index('source_frame')]))
 label=f'{e.kind}_{e.action_id}';folder=OUT/kind;folder.mkdir(exist_ok=True)
 field=np.max(q['w']*np.where(values>.001,values,0)[None,:],axis=1)
 verts=q['v'];faces=q['f'];size=np.ptp(verts,axis=0);center=(verts.max(0)+verts.min(0))/2
 fig=plt.figure(figsize=(8,5),facecolor='white');ax=fig.add_axes([.005,.12,.88,.77],projection='3d',proj_type='ortho')
 ax.add_collection3d(Poly3DCollection(verts[faces],facecolors=cmap(field[faces].mean(1)),edgecolors='none',antialiased=False,rasterized=True))
 for setter,c,s in zip([ax.set_xlim,ax.set_ylim,ax.set_zlim],center,size):setter(c-s*.52,c+s*.52)
 ax.set_box_aspect(size,zoom=1.2);ax.view_init(elev=22,azim=-65,roll=0);ax.set_axis_off()
 display={'finger':'Finger','robot_arm':'Robot arm','human_arm':'Human arm'}[kind]
 fig.text(.04,.94,f'{display}  /  {e.action_id}  /  {e.action_type.replace("_"," ")}',fontsize=14,weight='medium')
 fig.text(.04,.885,f'Measured frame {sf}   ·   action time {data["action_time"][idx]:.3f} s',color='#555555',fontsize=9)
 cb=fig.colorbar(plt.cm.ScalarMappable(norm=Normalize(0,1),cmap=cmap),cax=fig.add_axes([.91,.28,.017,.42]),ticks=[0,.25,.5,.75,1]);cb.outline.set_visible(False);cb.set_label('Normalized response (a.u.)',fontsize=9)
 fig.text(.04,.065,f'{len(values)} mapped channels   ·   smoothing {q["radius"]} mm   ·   fixed view 22° / −65°',fontsize=8,color='#555555')
 fig.text(.04,.029,'Reconstructed signal' if kind=='robot_arm' else 'Measured-frame processed signal',fontsize=8,color='#555555')
 png=folder/(label+'.png');fig.savefig(png,dpi=600,facecolor='white');plt.close(fig)
 thumb=Image.open(png).convert("RGB");thumb.thumbnail((800,500));thumb.save(folder/(label+'_preview.jpg'),quality=90)
 rec=dict(id=label,model=kind,action=e.action_type,image=str(png.relative_to(OUT)),source=str(e.path.relative_to(ROOT)),source_sha256=hashlib.sha256(e.path.read_bytes()).hexdigest(),model_asset=MODELS[kind][0],model_sha256=q['hash'],source_frame=sf,measured_frame_index=idx,measured_frame_count=len(a),action_time_s=float(data['action_time'][idx]),source_time_s=float(data['source_time'][idx]),local_density_score=float(scores[idx]),hotspot_channel=str(data['labels'].ravel()[hot]),hotspot_position_mm=q['p'][hot].tolist(),active_nodes_above_0_1=int((values>.1).sum()),missing_channels=int(np.isnan(raw[idx]).sum()),signal_values=[None if not np.isfinite(x) else float(x) for x in raw[idx]],mapping=q['mapping'].tolist(),camera=dict(elevation=22,azimuth=-65,roll=0,projection='orthographic'),smoothing_radius_mm=q['radius'])
 records.append(rec);print(f'{number+1}/60 {label} frame={sf} density={scores[idx]:.3f}',flush=True)
(OUT/'provenance.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
with (OUT/'index.csv').open('w') as f:
 keys=['id','model','action','image','source','source_frame','action_time_s','source_time_s','local_density_score','hotspot_channel','active_nodes_above_0_1','missing_channels'];w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows({k:r[k] for k in keys} for r in records)
for kind in MODELS:
 subset=[r for r in records if r['model']==kind];cols=4;rows=(len(subset)+cols-1)//cols;sheet=Image.new('RGB',(cols*600,rows*390),'white')
 for i,r in enumerate(subset):
  im=Image.open(OUT/r['image']);im.thumbnail((600,375));sheet.paste(im,((i%cols)*600,(i//cols)*390))
 sheet.save(OUT/(kind+'_overview.jpg'),quality=94)
cards=''.join(f'<a href="{r["image"]}"><img loading="lazy" src="{r["image"].replace(".png","_preview.jpg")}"><p>{html.escape(r["id"])} · {r["action"]}</p></a>' for r in records)
(OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>60 measured-frame 3D heatmaps</title><style>body{font:16px system-ui;margin:32px;background:#f5f6f8}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:18px}a{background:white;color:#123;text-decoration:none;padding:12px;border-radius:8px}img{width:100%}h1{font-size:25px}</style><h1>60 条数据 · 固定视角 3D heatmaps</h1><p>Finger 28 · Robot arm 3 · Human arm 29。点击图片打开 4800 × 3000 PNG。</p><main>'+cards+'</main>')
(OUT/'README.md').write_text('''# 全部动作的固定视角 3D heatmaps

共 60 张 4800 × 3000 PNG，600 DPI；按 finger（28）、robot_arm（3）、human_arm（29）分类。index.html 可浏览，index.csv / provenance.json 记录对应文件、采样帧号与时间。

选帧：仅使用 XLSX 原始采样时刻，读取与前端一致的处理信号。每个传感器及其 5 个空间最近的已映射测点构成局部邻域；选取局部平均响应最大的一帧，并以全场响应总和、较早时间依次打破平局。这是本批次“最密集”的操作定义。

使用前端当前 GH 导出的原始三角网格（包含 Robot arm 5 mm 和 Finger 3 mm 两端条带）。Human arm 每组 8 通道反序，Finger 使用前端原生 18→30 映射，Robot arm 使用 132 个 workbook 节点顺序。平滑与前端相同：max(value × smoothstep(1-distance/radius))，radius 分别为 25/3/10 mm，gain=1，threshold=0；统一 0–1 thermal 色标，无逐图拉伸。

所有图片正交相机 elev=22°、azim=-65°、roll=0°；模型尺寸适配画布，不更改模型朝向。图片由科学绘图器用前端网格重绘，非仪表盘 UI 截屏；三角面使用顶点场值平均着色，没有前端光照造成的信号颜色明暗变化。固定视角可能遮住背面热点，图中保留完整模型，不为单条数据旋转。

Robot arm 使用 Signal Reconstructed（原 Signal Recorded 全零），前后物理安装方向仍待校准；Finger 是几何显示映射，未代表物理接线校准。不同设备的归一化响应不是跨设备校准压力。原始缺失值记录为 null，仅渲染时不贡献场值；未映射的 Finger 交点无独立信号。
''')
print('Completed 60 images and gallery.',flush=True)
