import json
import Rhino.Geometry as rg
root='/Users/a0000/Desktop/tactile/outputs/finger-weave'
p=json.load(open(root+'/finger-woven-model.json'));v=p['geometry']['positions'];v=[v[i:i+3] for i in range(0,len(v),3)];ms=[]
for start,end,fa,fb in p['parts'][:20]:
 m=rg.Mesh()
 for point in v[start:end]:m.Vertices.Add(*point)
 for face in p['quads'][fa:fb]:m.Faces.AddFace(*[k-start for k in face])
 ms.append(m)
hits=[]
for i,m in enumerate(ms):
 for j in range(i+1,len(ms)):
  lines=rg.Intersect.Intersection.MeshMeshFast(m,ms[j])
  if lines:hits.append([i,j,len(lines)])
json.dump({'intersections':hits,'closed':all(m.IsClosed for m in ms)},open(root+'/validation.json','w'))
