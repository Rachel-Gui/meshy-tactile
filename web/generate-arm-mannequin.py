"""Build a posed, fitted display arm from the CC0 MakeHuman body topology.
Run with Python + numpy. Source attribution is in model-source/README.md.
"""
from pathlib import Path
import json, struct
import numpy as np

ROOT=Path(__file__).resolve().parent
vertices=[]; groups={}; group=''
for line in (ROOT/'model-source/human-base.obj').read_text().splitlines():
    if line.startswith('v '): vertices.append(list(map(float,line.split()[1:4])))
    elif line.startswith('g '): group=line.split()[1]
    elif line.startswith('f '): groups.setdefault(group,[]).append([int(s.split('/')[0])-1 for s in line.split()[1:]])
original=np.array(vertices)
def joint(name): return original[np.unique(sum(groups['joint-l-'+name],[]))].mean(axis=0)
wrist,elbow,shoulder=joint('hand'),joint('elbow'),joint('shoulder')
upperAxis=(shoulder-elbow)/np.linalg.norm(shoulder-elbow)
cut=1.42
faces=[f for f in groups['body'] if all(original[i,0]>2.0 and original[i,1]>0.8 and np.dot(original[i]-elbow,upperAxis)<cut for i in f)]
ids=sorted(set(sum(faces,[]))); remap={v:i for i,v in enumerate(ids)}
points=original[ids].copy(); faces=[[remap[i] for i in f] for f in faces]

# Flatten the upper-arm cut and close it with an ordered boundary cap.
edgeUses={}
for f in faces:
    for i,a in enumerate(f):edgeUses.setdefault(tuple(sorted((a,f[(i+1)%len(f)]))),[]).append((a,f[(i+1)%len(f)]))
boundary=[uses[0] for uses in edgeUses.values() if len(uses)==1]
links={a:b for a,b in boundary}
while links:
    first=next(iter(links));loop=[];current=first
    while current in links:
        loop.append(current);current=links.pop(current)
        if current==first:break
    if len(loop)>3 and np.mean((points[loop]-elbow)@upperAxis)>cut-.5:
        points[loop]+=(cut-(points[loop]-elbow)@upperAxis)[:,None]*upperAxis
        faces.append(loop[::-1])

def unit(v): return v/np.linalg.norm(v)
F=unit(elbow-wrist)
across=unit(joint('finger-5-1')-joint('finger-2-1'))
Y=-unit(across-F*np.dot(across,F)); Z=unit(np.cross(F,Y))
restF=np.column_stack([F,Y,Z])
# Spread existing anatomical fingers, with a gradual influence at the knuckle.
palmAxis=unit(np.mean([joint('finger-'+str(i)+'-1') for i in range(2,6)],axis=0)-wrist)
palmNormal=unit(np.cross(palmAxis,across))
# Subtle dorsal tendon relief, confined to the back of the hand.
handCenter=np.mean([joint('finger-'+str(i)+'-1') for i in range(2,6)],axis=0)*.55+wrist*.45
dorsal=(points-handCenter)@palmNormal
relief=np.zeros(len(points))
for digit in range(2,6):
    a=wrist*.75+joint('finger-'+str(digit)+'-1')*.25;b=joint('finger-'+str(digit)+'-1')
    axis=b-a;t=np.clip(((points-a)@axis)/np.dot(axis,axis),0,1)
    near=a+t[:,None]*axis
    lateral=(points-near)-((points-near)@palmNormal)[:,None]*palmNormal
    relief=np.maximum(relief,.008*np.exp(-np.sum(lateral*lateral,axis=1)/.004)*np.sin(t*np.pi))
points+=palmNormal*(relief*np.clip((dorsal-.04)/.05,0,1))[:,None]
# Preserve the source knuckle and web topology. Small rotations occur around
# the actual PIP/DIP pivots, not an arbitrary bend across an entire finger.
restPoints=points.copy()
for digit in range(2,6):
    root=joint('finger-'+str(digit)+'-1'); tip=joint('finger-'+str(digit)+'-4')
    axis=unit(tip-root)
    along=(restPoints-root)@axis
    closest=root+np.clip(along,0,np.linalg.norm(tip-root))[:,None]*axis
    lateral=np.linalg.norm(restPoints-closest,axis=1)
    # Smooth falloff prevents abrupt vertex reassignment between neighbours.
    influence=np.clip((.19-lateral)/.06,0,1)
    influence=influence*influence*(3-2*influence)
    influence*=np.clip(along/.22,0,1)
    for jointIndex, degrees in ((2,2.0+(digit-2)*.5),(3,1.0+(digit-2)*.3)):
        pivot=joint('finger-'+str(digit)+'-'+str(jointIndex))
        hinge=unit(np.cross(axis,palmNormal))
        distal=np.clip(((restPoints-pivot)@axis+.025)/.10,0,1)
        distal=distal*distal*(3-2*distal)
        theta=-np.deg2rad(degrees)*distal*influence
        rel=points-pivot
        points=pivot+rel*np.cos(theta)[:,None]+np.cross(hinge,rel)*np.sin(theta)[:,None]+(rel@hinge)[:,None]*hinge*(1-np.cos(theta))[:,None]
U=unit(shoulder-elbow); UY=unit(Y-U*np.dot(Y,U)); UZ=unit(np.cross(U,UY))
restU=np.column_stack([U,UY,UZ])
targetU=unit(np.array([0.20,0,0.98])); targetUY=np.array([0.,1.,0.]); targetUZ=np.cross(targetU,targetUY)
targetUFrame=np.column_stack([targetU,targetUY,targetUZ])
scale=305/np.linalg.norm(elbow-wrist)
targetW=np.array([-30.,0.,0.]); targetE=np.array([275.,0.,0.])
forearm=(points-wrist)@restF*scale+targetW
upper=((points-elbow)@restU)@targetUFrame.T*scale+targetE

# Blend two rigid anatomical segments only around their shared joint.
distU=np.linalg.norm(np.cross(points-elbow,U),axis=1)
distF=np.linalg.norm(np.cross(points-wrist,F),axis=1)
tU=(points-elbow)@U
tF=(points-wrist)@F
jointPlane=unit(U+F)
weightU=np.clip(((points-elbow)@jointPlane+.20)/.50,0,1)
weightU=weightU*weightU*(3-2*weightU)
posed=forearm*(1-weightU[:,None])+upper*weightU[:,None]

# Let the hand drop naturally from the wrist, maintaining its original
# anatomical joints/nails, rather than replacing fingers with capsules.
angle=np.deg2rad(-8)
rotation=np.array([[np.cos(angle),0,np.sin(angle)],[0,1,0],[-np.sin(angle),0,np.cos(angle)]])
twistAngle=np.deg2rad(55)
twist=np.array([[1,0,0],[0,np.cos(twistAngle),-np.sin(twistAngle)],[0,np.sin(twistAngle),np.cos(twistAngle)]])
weightH=np.clip((-forearm[:,0]-5)/42,0,1)
weightH=weightH*weightH*(3-2*weightH)
# Interpolate rotation angles, rather than blending rotated positions, to
# avoid narrowing the wrist when it turns into the hand.
rel=forearm-targetW
# Pronation is distributed along the forearm, rather than twisting the wrist.
weightTwist=np.clip((205-forearm[:,0])/225,0,1)
weightTwist=weightTwist*weightTwist*(3-2*weightTwist)
t=twistAngle*weightTwist;c=np.cos(t);s=np.sin(t)
turned=np.column_stack([rel[:,0],c*rel[:,1]-s*rel[:,2],s*rel[:,1]+c*rel[:,2]])
t=angle*weightH;c=np.cos(t);s=np.sin(t)
hand=np.column_stack([c*turned[:,0]+s*turned[:,2],turned[:,1],-s*turned[:,0]+c*turned[:,2]])+targetW
posed[weightTwist>0]=hand[weightTwist>0]

def subdivide(v,fs):
    facepoints=np.array([v[f].mean(axis=0) for f in fs]); edges={}; adjacent=[[] for _ in v]
    for fi,f in enumerate(fs):
        for i,a in enumerate(f):
            adjacent[a].append(fi); key=tuple(sorted((a,f[(i+1)%len(f)])))
            edges.setdefault(key,[]).append(fi)
    neighbours=[[] for _ in v];boundary=[[] for _ in v]
    for (a,b),flist in edges.items():
        neighbours[a].append(b);neighbours[b].append(a)
        if len(flist)==1: boundary[a].append(b);boundary[b].append(a)
    updated=v.copy()
    for i in range(len(v)):
        if len(boundary[i])==2: updated[i]=(6*v[i]+v[boundary[i]].sum(axis=0))/8
        elif adjacent[i]:
            n=len(adjacent[i]); avg=facepoints[adjacent[i]].mean(axis=0)
            mid=(v[neighbours[i]]+v[i]).mean(axis=0)/2
            updated[i]=(avg+2*mid+(n-3)*v[i])/n
    output=list(updated); edgeid={}
    for (a,b),flist in edges.items():
        edgeid[(a,b)]=len(output)
        output.append((v[a]+v[b]+facepoints[flist].sum(axis=0))/(2+len(flist)) if len(flist)==2 else (v[a]+v[b])/2)
    base=len(output);output.extend(facepoints);result=[]
    for fi,f in enumerate(fs):
        for i,a in enumerate(f):
            result.append([a,edgeid[tuple(sorted((a,f[(i+1)%len(f)])))],base+fi,edgeid[tuple(sorted((a,f[i-1])))]] )
    return np.array(output),result
posed=np.column_stack([posed,weightU])
for _ in range(2): posed,faces=subdivide(posed,faces)
weightU=posed[:,3].copy();posed=posed[:,:3]
# A clean, gently rounded display cut instead of an uneven shoulder remnant.
capDistance=(posed-targetE)@targetU
capEnd=np.percentile(capDistance[weightU>.98],99)
capBlend=np.clip((capDistance-(capEnd-20))/15,0,1)*(weightU>.98)
capBlend=capBlend*capBlend*(3-2*capBlend)
posed+=targetU*(capBlend*(capEnd-5-capDistance))[:,None]

# Keep all geometry inside the unchanged circular GH sleeve. Blend into the
# real wrist/elbow outside the sleeve, preserving hand anatomy and pose.
x=posed[:,0]; radius=np.hypot(posed[:,1],posed[:,2])
fitRegion=(x>-50)&(x<277)
blend=np.minimum(np.clip((x+50)/50,0,1),np.clip((277-x)/27,0,1))
blend=blend*blend*(3-2*blend);blend*=fitRegion*np.clip((.98-weightU)/.12,0,1)
targetRadius=35+27*np.clip(x,0,250)/250-1.7
ratio=1+blend*(targetRadius/np.maximum(radius,1e-6)-1)
posed[:,1:]*=ratio[:,None]

triangles=np.array([[f[0],f[j],f[j+1]] for f in faces for j in range(1,len(f)-1)],dtype=np.uint32)
normals=np.zeros_like(posed)
faceNormals=np.cross(posed[triangles[:,1]]-posed[triangles[:,0]],posed[triangles[:,2]]-posed[triangles[:,0]])
for col in range(3):np.add.at(normals,triangles[:,col],faceNormals)
normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
v=posed.astype('<f4');n=normals.astype('<f4');idx=triangles.astype('<u4')
binary=v.tobytes()+n.tobytes()+idx.tobytes()
doc={'asset':{'version':'2.0','generator':'Tactile anatomical arm / MakeHuman CC0'},'scene':0,
 'scenes':[{'nodes':[0]}],'nodes':[{'name':'Anatomical white arm','mesh':0}],
 'meshes':[{'primitives':[{'attributes':{'POSITION':0,'NORMAL':1},'indices':2,'material':0}]}],
 'materials':[{'name':'Satin white clay','pbrMetallicRoughness':{'baseColorFactor':[.93,.92,.90,1],'metallicFactor':0,'roughnessFactor':.62}}],
 'buffers':[{'byteLength':len(binary)}],
 'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':v.nbytes,'target':34962},{'buffer':0,'byteOffset':v.nbytes,'byteLength':n.nbytes,'target':34962},{'buffer':0,'byteOffset':v.nbytes+n.nbytes,'byteLength':idx.nbytes,'target':34963}],
 'accessors':[{'bufferView':0,'componentType':5126,'count':len(v),'type':'VEC3','min':v.min(0).tolist(),'max':v.max(0).tolist()},{'bufferView':1,'componentType':5126,'count':len(n),'type':'VEC3'},{'bufferView':2,'componentType':5125,'count':idx.size,'type':'SCALAR'}],
 'extras':{'units':'mm','source':'MakeHuman base.obj, CC0','displayModel':True}}
j=json.dumps(doc,separators=(',',':')).encode();j+=b' '*((-len(j))%4)
glb=struct.pack('<5I',0x46546c67,2,28+len(j)+len(binary),len(j),0x4e4f534a)+j+struct.pack('<2I',len(binary),0x004e4942)+binary
(ROOT/'public/assets/arm-mannequin.glb').write_bytes(glb)
print('Anatomical arm:',len(v),'vertices;',len(triangles),'triangles; bounds',v.min(0),v.max(0))
