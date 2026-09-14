# ARM_PLAIN_WEAVE_V1: closed ribbons following original GH centre curves.
import math
import Rhino.Geometry as rg
from System.Drawing import Color

lift=float(WeaveLift)
thickness=float(StripThickness)
width=float(StripWidth)
curves=[getattr(c,'Value',c) for c in list(RowCurves)+list(ColumnCurves)]
points=[getattr(p,'Value',p) for p in Points]
weave_meshes=[]
weave_checks=[]

def smooth(t):
    t=max(0.,min(1.,t))
    return t*t*t*(10+t*(-15+6*t))

for ci,curve in enumerate(curves):
    # Crossings are sorted geometrically along each strand, including end anchors.
    knots=[]
    for point in points:
        ok,t=curve.ClosestPoint(point)
        if ok and curve.PointAt(t).DistanceTo(point)<.02:
            knots.append((point.X,t))
    knots.sort()
    unique=[]
    for x,t in knots:
        if not unique or abs(x-unique[-1][0])>.02: unique.append((x,t))
    assert len(unique)==8,'Expected eight crossings per strand'
    family=1 if ci<12 else -1
    x0=curve.PointAtStart.X; x1=curve.PointAtEnd.X
    anchors=[(x0,family*lift)]
    for k,(x,t) in enumerate(unique):
        anchors.append((x,family*lift*(-1 if k%2==0 else 1)))
    if anchors[-1][0]<x1-.02: anchors.append((x1,anchors[-1][1]))
    def displacement(x):
        for k in range(len(anchors)-1):
            xa,ha=anchors[k]; xb,hb=anchors[k+1]
            if x<=xb:
                # Flat shoulders over the finite-width crossing; smooth bend between.
                q=(x-xa)/(xb-xa)
                u=smooth((q-.24)/.52)
                return ha+(hb-ha)*u
        return anchors[-1][1]
    mesh=rg.Mesh()
    steps=750
    for i in range(steps+1):
        x=x0+(x1-x0)*i/steps
        lo,hi=curve.Domain.T0,curve.Domain.T1
        for _ in range(32):
            mid=(lo+hi)/2
            if curve.PointAt(mid).X<x: lo=mid
            else: hi=mid
        t=(lo+hi)/2
        p=curve.PointAt(t)
        r=math.hypot(p.Y,p.Z)
        normal=rg.Vector3d(-.108,p.Y/r,p.Z/r);normal.Unitize()
        tangent=curve.TangentAt(t);tangent.Unitize()
        lateral=rg.Vector3d.CrossProduct(normal,tangent);lateral.Unitize()
        h=displacement(x)
        for side,depth in [(-1,-1),(1,-1),(-1,1),(1,1)]:
            q=p+lateral*(side*width/2)+normal*(h+depth*thickness/2)
            mesh.Vertices.Add(q)
    for i in range(steps):
        a=4*i;b=a+4
        mesh.Faces.AddFace(a,a+1,b+1,b)
        mesh.Faces.AddFace(a+2,b+2,b+3,a+3)
        mesh.Faces.AddFace(a,b,b+2,a+2)
        mesh.Faces.AddFace(a+1,a+3,b+3,b+1)
    mesh.Faces.AddFace(0,2,3,1)
    a=4*steps;mesh.Faces.AddFace(a,a+1,a+3,a+2)
    mesh.UnifyNormals();mesh.Normals.ComputeNormals();mesh.Compact()
    if mesh.SolidOrientation()<0: mesh.Flip(True,True,True)
    mesh.VertexColors.CreateMonotoneMesh(Color.FromArgb(20,30,110))
    weave_meshes.append(mesh)
    weave_checks.append({'family':'A' if ci<12 else 'B','index':ci%12,'crossings':len(unique),'heights':[displacement(x) for x,t in unique]})
HeatMesh=rg.Mesh()
for mesh in weave_meshes: HeatMesh.Append(mesh)
# Same 5 mm end widths. The cuffs bridge both woven layers at their anchors.
for start,end in [(0,float(EndBandWidth)),(250-float(EndBandWidth),250)]:
    band=rg.Mesh();segments=256
    for x,h in [(start,-lift-thickness/2),(end,-lift-thickness/2),(start,lift+thickness/2),(end,lift+thickness/2)]:
        radius=35+.108*x+h
        for i in range(segments):
            theta=2*math.pi*i/segments
            band.Vertices.Add(x,radius*math.cos(theta),radius*math.sin(theta))
    for i in range(segments):
        j=(i+1)%segments
        band.Faces.AddFace(i,j,segments+j,segments+i)
        band.Faces.AddFace(2*segments+i,3*segments+i,3*segments+j,2*segments+j)
        band.Faces.AddFace(i,2*segments+i,2*segments+j,j)
        band.Faces.AddFace(segments+i,segments+j,3*segments+j,3*segments+i)
    band.UnifyNormals();band.Normals.ComputeNormals()
    if band.SolidOrientation()<0: band.Flip(True,True,True)
    band.VertexColors.CreateMonotoneMesh(Color.FromArgb(20,30,110))
    weave_meshes.append(band);HeatMesh.Append(band)
HeatMesh.Normals.ComputeNormals();HeatMesh.Compact()
Status='OK | plain weave | 24 closed strips | 96 alternating crossings | lift %.2f mm | thickness %.2f mm' % (lift,thickness)
