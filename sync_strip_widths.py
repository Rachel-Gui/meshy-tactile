"""Rhino 8 RunPythonScript: set both strip families to 4 mm and export."""
import os, json, shutil, traceback
import System
import Rhino
import Grasshopper as gh
from Grasshopper.Kernel import GH_DocumentIO, GH_RuntimeMessageLevel
ROOT = os.path.dirname(os.path.abspath(__file__))

def run():
    Rhino.RhinoApp.RunScript('_Grasshopper', False)
    report = {}
    for filename, expected in (('ring.gh', 30), ('1.gh', 96)):
        path = os.path.join(ROOT, filename)
        io = GH_DocumentIO()
        assert io.Open(path)
        doc = io.Document
        doc.Enabled = True
        divisions = [obj for obj in doc.Objects if obj.Name == 'Division']
        assert len(divisions) == 2
        before = []
        for division in divisions:
            width = division.Params.Input[0].Sources[0]
            divisor = division.Params.Input[1].Sources[0]
            before.append(2 * float(width.CurrentValue) / float(divisor.CurrentValue))
            assert width.NickName == 'Strip Width'
            width.SetSliderValue(System.Decimal(4))
            divisor.SetSliderValue(System.Decimal(2))
        doc.NewSolution(False)
        offsets = []
        errors = []
        for obj in doc.Objects:
            if obj.Name == 'Offset on Srf':
                offsets.extend(float(v.Value) for v in obj.Params.Input[1].VolatileData.AllData(True))
            if hasattr(obj, 'RuntimeMessages'):
                errors.extend(str(v) for v in obj.RuntimeMessages(GH_RuntimeMessageLevel.Error))
        assert len(offsets) == 4 and all(abs(abs(v) - 2) < 0.000001 for v in offsets)
        assert not errors, repr(errors)
        named = {obj.NickName.strip(): obj for obj in doc.Objects}
        sensors = list(named['SensorIntersections'].VolatileData.AllData(True))
        meshes = [v.Value for v in named['HeatmapMesh'].VolatileData.AllData(True)]
        assert len(sensors) == expected and meshes
        assert all(m.IsValid and m.VertexColors.Count == m.Vertices.Count for m in meshes)
        if any(abs(value - 4) > 0.000001 for value in before):
            backup = os.path.join(ROOT, filename[:-3] + '.before-width4.gh')
            if not os.path.exists(backup):
                shutil.copy2(path, backup)
            saved = GH_DocumentIO()
            saved.Document = doc
            assert saved.SaveQuiet(path)
        gh.Instances.DocumentServer.AddDocument(doc)
        gh.Instances.ActiveCanvas.Document = doc
        script = os.path.join(ROOT, 'web', 'export_ring_model.py' if filename == 'ring.gh' else 'export_grasshopper_model.py')
        execfile(script, {'__name__': '__main__', '__file__': script})
        report[filename] = {'beforeWidth': before, 'stripWidth': 4, 'offsets': offsets,
            'sensorCount': len(sensors), 'vertexCount': sum(m.Vertices.Count for m in meshes),
            'runtimeErrors': errors, 'exported': True}
    Rhino.RhinoDoc.ActiveDoc.Views.Redraw()
    with open(os.path.join(ROOT, 'strip-width-validation.json'), 'w') as output:
        json.dump(report, output, indent=2)

try:
    run()
except:
    with open(os.path.join(ROOT, 'width-sync-error.txt'), 'w') as output:
        output.write(traceback.format_exc().encode('utf-8'))
