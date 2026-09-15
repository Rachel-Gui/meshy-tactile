from pathlib import Path
from PIL import Image,ImageDraw
import zipfile,numpy as np
root=Path(__file__).resolve().parent;files=sorted(root.glob('human_*.png'))+sorted(root.glob('robot_*.png'))+sorted(root.glob('finger_*_AB_*.png'));cols=4
canvas=Image.new('RGB',(1600,((len(files)+cols-1)//cols)*420),'#e8ebef');draw=ImageDraw.Draw(canvas)
for i,f in enumerate(files):
 im=Image.open(f);im.thumbnail((400,390));xy=(i%cols*400,i//cols*420);canvas.paste(im,xy,im);draw.text((xy[0]+5,xy[1]+396),f.stem.replace('_frame_',' f'),fill='#17212b')
canvas.save(root/'overview.jpg',quality=95)
allfiles=sorted(root.glob('*.png'));assert len(allfiles)==60
for f in allfiles:
 im=Image.open(f);assert im.mode=='RGBA' and im.size==(3200,3200);assert im.getchannel('A').getextrema()==(0,255)
 bbox=im.getchannel('A').getbbox();assert bbox and min(bbox[:2])>0 and max(bbox[2:])<3200
 assert np.any(np.asarray(im)[:,:,1]>100),f
(root/'README.txt').write_text('Final delivery key frames\n\n60 transparent PNGs, 3200 x 3200 pixels.\n9 Human arm key frames from the new delivery.\n3 Robot arm frames: RB004 257, RB003 538, RB001 887.\n16 Finger synchronized A/B views, plus 32 individual A or B views.\nFile names retain sequence, position, orientation, sleeve and zero-based frame.\nOriginal signal values and mapped node order are unchanged.\nFinger uses the actual website A/B heatmap module, radius 3 mm, angles 0 degrees. Robot uses radius 10 mm. Display gain 1.8 and threshold 0 throughout. Raw source signals remain unchanged. Finger rear surfaces stay opaque; front low-signal surfaces use 18% opacity, increasing with heat intensity.\nThe camera is fixed within each model/view category. Back-facing data remains on its true side; data was not rotated for screenshots.\nframes.json records source frame references.\n')
for name,selected in [('all-keyframes-hd-transparent.zip',allfiles),('human-arm-keyframes.zip',sorted(root.glob('human_*.png'))),('robot-arm-keyframes.zip',sorted(root.glob('robot_*.png'))),('finger-keyframes.zip',sorted(root.glob('finger_*.png')))]:
 with zipfile.ZipFile(root/name,'w',zipfile.ZIP_DEFLATED) as z:
  for f in selected+[root/'frames.json',root/'README.txt']:z.write(f,f.name)
print('Validated all 60 PNGs: transparent, 3200 square, nonempty and no clipped model bounds.')
