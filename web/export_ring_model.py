"""Run in Rhino 8 with _-RunPythonScript to export ring.gh for the frontend.

Sensor indices preserve the GH SensorIntersections order, without applying
the arm model's channel reversal. Physical channel calibration is separate.
"""
import hashlib
import json
import math
import os
import traceback

import Rhino
import Rhino.Geometry as rg
import Grasshopper as gh
from Grasshopper.Kernel import GH_DocumentIO

ROOT = os.path.dirname(os.path.abspath(__file__))
DEFINITION = os.path.join(os.path.dirname(ROOT), 'ring.gh')
OUTPUT = os.path.join(ROOT, 'public', 'assets', 'ring-model.json')


def values(parameter):
    return [getattr(v, 'Value', v) for v in parameter.VolatileData.AllData(True)]


def export():
    Rhino.RhinoApp.RunScript('_Grasshopper', False)
    io = GH_DocumentIO()
    assert io.Open(DEFINITION), 'Cannot open ring.gh'
    document = io.Document
    document.Enabled = True
    document.NewSolution(False)
    objects = list(document.Objects)
    named = {obj.NickName.strip(): obj for obj in objects}
    mesh = rg.Mesh()
    for part in values(named['HeatmapMesh']):
        mesh.Append(part)
    sensors = values(named['SensorIntersections'])
    assert len(sensors) == 30, 'Expected 30 internal crossings'
    assert mesh.IsValid and mesh.Faces.Count > 0, 'Heatmap mesh is empty or invalid'
    mesh.Normals.ComputeNormals()
    assert mesh.VertexColors.Count == mesh.Vertices.Count
    positions, normals, colors, indices = [], [], [], []
    for i in range(mesh.Vertices.Count):
        vertex, normal, color = mesh.Vertices[i], mesh.Normals[i], mesh.VertexColors[i]
        positions.extend(round(float(v), 6) for v in (vertex.X, vertex.Y, vertex.Z))
        normals.extend(round(float(v), 6) for v in (normal.X, normal.Y, normal.Z))
        colors.extend(round(v / 255.0, 6) for v in (color.R, color.G, color.B))
    for face in mesh.Faces:
        indices.extend((int(face.A), int(face.B), int(face.C)))
        if face.IsQuad:
            indices.extend((int(face.A), int(face.C), int(face.D)))

    # Use actual crossing tangents, not the arm model's 12x8 neighbours.
    families = [values(obj.Params.Output[0]) for obj in objects if obj.Name == 'Pull Curve']
    assert len(families) == 2
    def tangent(point, curves):
        candidates = []
        for curve in curves:
            success, t = curve.ClosestPoint(point)
            if success:
                candidates.append((point.DistanceTo(curve.PointAt(t)), curve.TangentAt(t)))
        distance, direction = min(candidates, key=lambda item: item[0])
        assert distance < 0.02, 'Sensor is not on a strip centreline'
        direction.Unitize()
        return direction

    sensor_payload = []
    for index, point in enumerate(sensors):
        a, b = (tangent(point, family) for family in families)
        angle = math.degrees(math.acos(min(1.0, abs(a * b))))
        sensor_payload.append({
            'index': index,
            'position': [round(v, 6) for v in (point.X, point.Y, point.Z)],
            'crossingAngle': round(angle, 3),
        })
    with open(DEFINITION, 'rb') as source:
        digest = hashlib.sha256(source.read()).hexdigest()
    offsets = [abs(float(value)) for obj in objects if obj.Name == 'Offset on Srf'
               for value in values(obj.Params.Input[1])]
    assert offsets and max(offsets) - min(offsets) < 0.000001
    payload = {
        'metadata': {
            'source': 'ring.gh', 'sourceSha256': digest,
            'coordinateSystem': 'Rhino Z-up', 'units': 'mm',
            'stripWidth': offsets[0] * 2,
            'sensorOrder': 'SensorIntersections GH list order',
            'sensorCount': len(sensors), 'vertexCount': mesh.Vertices.Count,
            'faceCount': mesh.Faces.Count, 'triangleCount': len(indices) // 3,
            'length': float(named['Length'].CurrentValue),
            'frontDiameter': 2 * float(named['Radius small'].CurrentValue),
            'rearDiameter': 2 * float(named['Radius large'].CurrentValue),
            'heatRadius': 3,
        },
        'geometry': {'positions': positions, 'normals': normals, 'colors': colors, 'indices': indices},
        'sensors': sensor_payload,
    }
    with open(OUTPUT, 'w') as target:
        json.dump(payload, target, separators=(',', ':'))
    document.Dispose()
    print('Exported ring.gh: {} vertices, {} sensors'.format(mesh.Vertices.Count, len(sensors)))


if __name__ == '__main__':
    try:
        export()
    except:
        with open(os.path.join(ROOT, 'ring-export-error.txt'), 'w') as error_file:
            error_file.write(traceback.format_exc().encode('utf-8'))
        raise
