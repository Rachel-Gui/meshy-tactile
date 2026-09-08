import os
import traceback
import System
import System.Drawing as drawing
import Rhino
import Grasshopper as gh
from Grasshopper.Kernel import GH_DocumentIO, GH_RuntimeMessageLevel
ROOT = r'C:\Users\Ruich\Desktop\tactile\meshy-tactile'

def run():
    io = GH_DocumentIO()
    assert io.Open(os.path.join(ROOT, 'ring.gh'))
    doc = io.Document
    gh.Instances.DocumentServer.AddDocument(doc)
    gh.Instances.ActiveCanvas.Document = doc
    doc.Enabled = True
    doc.NewSolution(False)
    objects = list(doc.Objects)
    assert len(objects) == 73
    def mesh():
        return list(objects[67].VolatileData.AllData(True))[0].Value
    points = [v.Value for v in objects[64].VolatileData.AllData(True)]
    assert len(points) == 30
    assert all(0.01 < p.X < 26.99 for p in points)
    assert min(points[i].DistanceTo(points[j]) for i in range(30) for j in range(i)) > 0.01
    saved_value = objects[53].CurrentValue
    try:
        objects[53].SetSliderValue(System.Decimal(0))
        doc.NewSolution(False)
        zero_colors = set(c.ToArgb() for c in mesh().VertexColors)
        assert len(zero_colors) == 1
        objects[53].SetSliderValue(System.Decimal(1))
        doc.NewSolution(False)
        active_colors = set(c.ToArgb() for c in mesh().VertexColors)
        assert len(active_colors) > 10 and active_colors != zero_colors
    finally:
        objects[53].SetSliderValue(saved_value)
        doc.NewSolution(False)
    final_mesh = mesh()
    assert final_mesh.IsValid
    errors = []
    for obj in doc.Objects:
        if hasattr(obj, 'RuntimeMessages'):
            errors.extend(str(x) for x in obj.RuntimeMessages(GH_RuntimeMessageLevel.Error))
    assert not errors
    views = list(Rhino.RhinoDoc.ActiveDoc.Views)
    view = next((v for v in views if v.ActiveViewport.IsPerspectiveProjection), views[0])
    Rhino.RhinoDoc.ActiveDoc.Views.ActiveView = view
    view.ActiveViewport.ZoomBoundingBox(final_mesh.GetBoundingBox(True))
    view.Redraw()
    capture = Rhino.Display.ViewCapture()
    capture.Width = 1400
    capture.Height = 1000
    capture.DrawAxes = False
    capture.DrawGrid = False
    capture.DrawGridAxes = False
    bmp = capture.CaptureToBitmap(view)
    assert bmp is not None
    bmp.Save(os.path.join(ROOT, 'ring-heatmap-preview.png'), drawing.Imaging.ImageFormat.Png)
    bmp.Dispose()
    with open(os.path.join(ROOT, 'ring-validation.txt'), 'a') as out:
        out.write('\nReopened saved .gh: PASS\n30 unique internal points: PASS\nZero input => one baseline color: PASS\nUnit input => {} colors: PASS\nOriginal value {} restored\nViewport capture: ring-heatmap-preview.png\n'.format(len(active_colors), saved_value))

try:
    run()
except:
    with open(os.path.join(ROOT, 'ring-verify-error.txt'), 'w') as out:
        out.write(traceback.format_exc().encode('utf-8'))
