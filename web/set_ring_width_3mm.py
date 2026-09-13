"""Run in Rhino: change only Ring strip width to 3 mm and export the solved mesh."""
import os
import json
import shutil
import traceback
import System
import Rhino
from Grasshopper.Kernel import GH_DocumentIO, GH_RuntimeMessageLevel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, 'Archive', 'validation_reports', 'ring-width-3mm.json')

def run():
    path = os.path.join(ROOT, 'models', 'tactile', 'ring.gh')
    io = GH_DocumentIO()
    assert io.Open(path), 'Cannot open ring.gh'
    doc = io.Document
    doc.Enabled = True
    divisions = [obj for obj in doc.Objects if obj.Name == 'Division']
    assert len(divisions) == 2
    before = []
    for division in divisions:
        width = division.Params.Input[0].Sources[0]
        divisor = division.Params.Input[1].Sources[0]
        assert width.NickName == 'Strip Width'
        before.append(2 * System.Convert.ToDouble(width.CurrentValue) / System.Convert.ToDouble(divisor.CurrentValue))
        width.SetSliderValue(System.Decimal(3))
        divisor.SetSliderValue(System.Decimal(2))
    doc.NewSolution(False)
    offsets, errors = [], []
    for obj in doc.Objects:
        if obj.Name == 'Offset on Srf':
            offsets.extend(float(v.Value) for v in obj.Params.Input[1].VolatileData.AllData(True))
        if hasattr(obj, 'RuntimeMessages'):
            errors.extend(str(v) for v in obj.RuntimeMessages(GH_RuntimeMessageLevel.Error))
    assert len(offsets) == 4 and all(abs(abs(v) - 1.5) < 0.000001 for v in offsets), repr(offsets)
    assert not errors, repr(errors)
    named = {obj.NickName.strip(): obj for obj in doc.Objects}
    sensors = list(named['SensorIntersections'].VolatileData.AllData(True))
    meshes = [v.Value for v in named['HeatmapMesh'].VolatileData.AllData(True)]
    assert len(sensors) == 30 and meshes
    assert all(m.IsValid and m.VertexColors.Count == m.Vertices.Count for m in meshes)
    backup = os.path.join(ROOT, 'Archive', 'model_backups', 'ring.before-width3.gh')
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
    saved = GH_DocumentIO()
    saved.Document = doc
    assert saved.SaveQuiet(path)
    doc.Dispose()
    exporter = os.path.join(ROOT, 'web', 'export_ring_model.py')
    namespace = {'__name__': 'ring_export', '__file__': exporter}
    exec(compile(open(exporter).read(), exporter, 'exec'), namespace)
    namespace['export']()
    report = {'beforeWidth': before, 'stripWidth': 3, 'offsets': offsets, 'sensorCount': 30, 'runtimeErrors': errors, 'exported': True}
    with open(REPORT, 'w') as output:
        json.dump(report, output, indent=2)
    print(json.dumps(report))

try:
    run()
except:
    with open(REPORT + '.error.txt', 'w') as output:
        output.write(traceback.format_exc())
    raise
