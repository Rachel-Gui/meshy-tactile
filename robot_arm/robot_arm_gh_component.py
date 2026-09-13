"""Grasshopper component: equal-end woven sleeve with 132 interior crossings.
Inputs: Length, FrontRadius, RearRadius, StripWidth, MeshSize.
Outputs: Status (JSON), HeatMesh. Geometry is in millimetres, X longitudinal.
"""
import math,json
import Rhino.Geometry as rg
from System.Drawing import Color
L=float(Length);r0=float(FrontRadius);r1=float(RearRadius);width=float(StripWidth);resolution=float(MeshSize)
assert L>0 and min(r0,r1)>0 and width>0
N=12
COL=[1,10,12,6,2,3,7,11,5,8,9,4]
ROW=[6,1,4,2,9,7,11,10,3,12,5,8]
steps=max(120,int(math.ceil(L/max(.25,resolution))))
mesh=rg.Mesh()
# Equal/opposite half turns: intersections at t = 1/12 ... 11/12.
# Width follows the local surface normal to the ribbon centreline.
for family in [-1,1]:
 for c in range(N):
  start=mesh.Vertices.Count
  for k in range(steps+1):
   t=float(k)/steps;r=r0+(r1-r0)*t;theta=2*math.pi*c/N+family*math.pi*t
   axial=math.sqrt(L*L+(r1-r0)**2);circ=family*math.pi*r
   denom=math.sqrt(axial*axial+circ*circ)
   # Displace perpendicular to tangent in the developed surface.
   for side in [-1,1]:
    dt=side*width*.5*(-circ/denom)/axial
    tt=max(0,min(1,t+dt));rr=r0+(r1-r0)*tt
    angle=theta+side*width*.5*(axial/denom)/r
    mesh.Vertices.Add(L*tt,rr*math.cos(angle),rr*math.sin(angle))
  for k in range(steps):
   j=start+2*k;mesh.Faces.AddFace(j,j+2,j+3,j+1)
mesh.Normals.ComputeNormals();mesh.Compact()
for i in range(mesh.Vertices.Count):mesh.VertexColors.Add(Color.FromArgb(20,30,110))
sensors=[]
# Row-major display order matches the viewer and browser action export.
for slot in range(1,N):
 for c in range(N):
  t=float(slot)/N;r=r0+(r1-r0)*t;theta=2*math.pi*c/N+math.pi*t
  row=(c+slot)%N
  angle=2*math.degrees(math.atan(math.pi*r/math.sqrt(L*L+(r1-r0)**2)))
  sensors.append({'index':len(sensors),'displayRow':slot,'displayColumn':c+1,'node':'C%dR%d'%(COL[c],ROW[row]),'physicalRowPort':2*ROW[row]-1,'physicalColumnPort':2*COL[c]-1,'position':[L*t,r*math.cos(theta),r*math.sin(theta)],'crossingAngle':angle})
HeatMesh=mesh
Status=json.dumps({'length':L,'frontDiameter':2*r0,'rearDiameter':2*r1,'stripWidth':width,'sensorCount':132,'rows':11,'columns':12,'units':'mm','coordinateSystem':'Rhino Z-up','colOrder':COL,'rowOrder':ROW,'geometryMethod':'Opposite half-turn surface helices; 11 interior crossings per COL; coincident end pairs excluded','sensors':sensors})

bl=float(Length);br0=float(FrontRadius);br1=float(RearRadius)

# ROBOT_FINGER_END_BANDS_V1
if HeatMesh is not None:
    bw = float(EndBandWidth)
    assert 0 < bw < bl / 2
    band_start_vertex = HeatMesh.Vertices.Count
    for start, end in [(0,bw),(bl-bw,bl)]:
        band = rg.Mesh()
        segments = 192
        for x, inset in [(start,0),(end,0),(start,0.2),(end,0.2)]:
            radius = br0+(br1-br0)*x/bl+0.3-inset
            for i in range(segments):
                angle = 2*math.pi*i/segments
                band.Vertices.Add(x,radius*math.cos(angle),radius*math.sin(angle))
        for i in range(segments):
            j=(i+1)%segments
            band.Faces.AddFace(i,j,segments+j,segments+i)
            band.Faces.AddFace(2*segments+i,3*segments+i,3*segments+j,2*segments+j)
            band.Faces.AddFace(i,2*segments+i,2*segments+j,j)
            band.Faces.AddFace(segments+i,segments+j,3*segments+j,3*segments+i)
        band.Normals.ComputeNormals()
        for i in range(band.Vertices.Count):
            band.VertexColors.Add(Color.FromArgb(20,30,110))
        HeatMesh.Append(band)
    HeatMesh.Normals.ComputeNormals()
    HeatMesh.Compact()
    band_meta=json.loads(Status);band_meta.update({'endBandWidth':bw,'endBandCount':2,'bandStartVertex':band_start_vertex});Status=json.dumps(band_meta)
