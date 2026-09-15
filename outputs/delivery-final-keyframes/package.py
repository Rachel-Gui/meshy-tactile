from pathlib import Path
from PIL import Image,ImageDraw
import zipfile,numpy as np
root=Path(__file__).resolve().parent;files=sorted(root.glob('robot_*.png'))+sorted(root.glob('finger_*_AB_*.png'));cols=4
canvas=Image.new('RGB',(1600,((len(files)+cols-1)//cols)*420),'#e8ebef');draw=ImageDraw.Draw(canvas)
for i,f in enumerate(files):
 im=Image.open(f);im.thumbnail((400,390));xy=(i%cols*400,i//cols*420);canvas.paste(im,xy,im);draw.text((xy[0]+5,xy[1]+396),f.stem.replace('_frame_',' f'),fill='#17212b')
canvas.save(root/'overview.jpg',quality=95)
allfiles=sorted(root.glob('*.png'));assert len(allfiles)==51
for f in allfiles:
 im=Image.open(f);assert im.mode=='RGBA' and im.size==(2400,2400);assert im.getchannel('A').getextrema()==(0,255)
 bbox=im.getchannel('A').getbbox();assert bbox and min(bbox[:2])>0 and max(bbox[2:])<2400
 assert np.any(np.asarray(im)[:,:,1]>100),f
(root/'README.txt').write_text('Final delivery key frames\n\n51 transparent PNGs, 2400 x 2400 pixels.\n3 Robot arm frames: RB004 257, RB003 538, RB001 887.\n16 Finger synchronized A/B views, plus 32 individual A or B views.\nFile names retain sequence, position, orientation, sleeve and zero-based frame.\nOriginal signal values and mapped node order are unchanged.\nFinger uses the actual website A/B heatmap module, radius 3 mm, angles 0 degrees. Robot uses radius 10 mm. Gain 1 and threshold 0 throughout.\nThe camera is fixed within each model/view category. Back-facing data remains on its true side; data was not rotated for screenshots.\nframes.json records source frame references.\n')
for name,selected in [('all-keyframes-hd-transparent.zip',allfiles),('robot-arm-keyframes.zip',sorted(root.glob('robot_*.png'))),('finger-keyframes.zip',sorted(root.glob('finger_*.png')))]:
 with zipfile.ZipFile(root/name,'w',zipfile.ZIP_DEFLATED) as z:
  for f in selected+[root/'frames.json',root/'README.txt']:z.write(f,f.name)
print('Validated all 51 PNGs: transparent, 2400 square, nonempty and no clipped model bounds.')
