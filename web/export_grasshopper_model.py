"""Export the active Grasshopper heatmap mesh and ordered sensor points to JSON.

Run with Rhino 8's ``rhinocode`` CLI while Rhino and the Grasshopper definition
are open. The generated JSON is consumed directly by the local Three.js UI.
"""

import os
import hashlib
import json

import Grasshopper
import Rhino.Geometry as rg
from Grasshopper import Instances


OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'public', 'assets', 'model.json')
ROWS = 12
COLUMNS = 8
SENSOR_COUNT = ROWS * COLUMNS


def gh_values(parameter):
    return [
        getattr(item, "Value", item)
        for item in parameter.VolatileData.AllData(True)
    ]


def find_object(document, nickname):
    for item in document.Objects:
        if getattr(item, "NickName", "").strip() == nickname:
            return item
    raise RuntimeError("Grasshopper object {!r} was not found".format(nickname))


def find_python_component(document):
    for item in document.Objects:
        if getattr(item, "NickName", "").strip() == "Sensor Heatmap":
            return item
    raise RuntimeError("Sensor Heatmap Python component was not found")


def parameter_by_name(parameters, name):
    for parameter in parameters:
        if parameter.Name == name:
            return parameter
    raise RuntimeError("Python parameter {!r} was not found".format(name))


def closest_curve_index(point, curves):
    best_index = -1
    best_distance = float("inf")

    for curve_index, curve in enumerate(curves):
        success, parameter = curve.ClosestPoint(point)
        if not success:
            continue

        distance = point.DistanceTo(curve.PointAt(parameter))
        if distance < best_distance:
            best_index = curve_index
            best_distance = distance

    return best_index, best_distance


def order_sensor_points(points, row_curves, column_curves):
    if len(points) != SENSOR_COUNT:
        raise RuntimeError("Expected 96 sensor points, received {}".format(len(points)))
    if len(row_curves) != ROWS or len(column_curves) != ROWS:
        raise RuntimeError("Expected 12 RowCurves and 12 ColumnCurves")

    slots = [None] * SENSOR_COUNT
    bounding_box = rg.BoundingBox(points)
    tolerance = max(0.01, bounding_box.Diagonal.Length * 0.0001)

    for point in points:
        row_index, row_distance = closest_curve_index(point, row_curves)
        column_index, column_distance = closest_curve_index(point, column_curves)

        if row_distance > tolerance or column_distance > tolerance:
            raise RuntimeError("A sensor point is not on both curve families")

        cyclic_offset = (column_index - row_index) % ROWS
        if not 1 <= cyclic_offset <= COLUMNS:
            raise RuntimeError(
                "Invalid cyclic offset {} at A{} x B{}".format(
                    cyclic_offset,
                    row_index,
                    column_index,
                )
            )

        slot_index = row_index * COLUMNS + cyclic_offset - 1
        if slots[slot_index] is not None:
            raise RuntimeError("Duplicate sensor slot {}".format(slot_index))
        slots[slot_index] = point

    if any(point is None for point in slots):
        raise RuntimeError("The sensor map contains missing slots")

    return slots


def mesh_payload(mesh):
    mesh = mesh.DuplicateMesh()
    mesh.Normals.ComputeNormals()
    mesh.Compact()

    positions = []
    normals = []
    colors = []
    indices = []

    has_colors = mesh.VertexColors.Count == mesh.Vertices.Count

    for vertex_index in range(mesh.Vertices.Count):
        vertex = mesh.Vertices[vertex_index]
        normal = mesh.Normals[vertex_index]
        positions.extend((float(vertex.X), float(vertex.Y), float(vertex.Z)))
        normals.extend((float(normal.X), float(normal.Y), float(normal.Z)))

        if has_colors:
            color = mesh.VertexColors[vertex_index]
            colors.extend((color.R / 255.0, color.G / 255.0, color.B / 255.0))
        else:
            colors.extend((0.08, 0.12, 0.32))

    for face in mesh.Faces:
        indices.extend((int(face.A), int(face.B), int(face.C)))
        if face.IsQuad:
            indices.extend((int(face.A), int(face.C), int(face.D)))

    bounding_box = mesh.GetBoundingBox(True)

    return {
        "positions": positions,
        "normals": normals,
        "colors": colors,
        "indices": indices,
        "bounds": {
            "min": [bounding_box.Min.X, bounding_box.Min.Y, bounding_box.Min.Z],
            "max": [bounding_box.Max.X, bounding_box.Max.Y, bounding_box.Max.Z],
        },
    }


document = Instances.ActiveCanvas.Document if Instances.ActiveCanvas else None
if document is None:
    raise RuntimeError("Open Grasshopper and 1.gh first")

if os.path.basename(document.FilePath) != '1.gh':
    raise RuntimeError(
        "The active Grasshopper document is not tactile/1.gh: {}".format(
            document.FilePath
        )
    )

heatmap_parameter = find_object(document, "HeatmapMesh")
heatmap_meshes = [item for item in gh_values(heatmap_parameter) if isinstance(item, rg.Mesh)]
if not heatmap_meshes:
    raise RuntimeError("HeatmapMesh has no mesh data")

heatmap_mesh = rg.Mesh()
for item in heatmap_meshes:
    heatmap_mesh.Append(item)

sensor_parameter = find_object(document, "SensorIntersections")
raw_sensor_points = [
    item for item in gh_values(sensor_parameter) if isinstance(item, rg.Point3d)
]

python_component = find_python_component(document)
row_curves = gh_values(parameter_by_name(python_component.Params.Input, "RowCurves"))
column_curves = gh_values(parameter_by_name(python_component.Params.Input, "ColumnCurves"))
sensor_points = order_sensor_points(raw_sensor_points, row_curves, column_curves)

offsets = [abs(float(value)) for obj in document.Objects if obj.Name == 'Offset on Srf'
           for value in gh_values(obj.Params.Input[1])]
assert offsets and max(offsets) - min(offsets) < 0.000001
with open(document.FilePath, 'rb') as source:
    source_hash = hashlib.sha256(source.read()).hexdigest()
payload = {
    "metadata": {
        "source": os.path.basename(document.FilePath),
        "sourceSha256": source_hash,
        "stripWidth": offsets[0] * 2,
        "units": "mm",
        "coordinateSystem": "Rhino Z-up",
        "rows": ROWS,
        "columns": COLUMNS,
        "sensorCount": SENSOR_COUNT,
        "vertexCount": heatmap_mesh.Vertices.Count,
        "faceCount": heatmap_mesh.Faces.Count,
    },
    "geometry": mesh_payload(heatmap_mesh),
    "sensors": [
        {
            "index": sensor_index,
            "row": sensor_index // COLUMNS,
            "column": sensor_index % COLUMNS,
            "position": [point.X, point.Y, point.Z],
        }
        for sensor_index, point in enumerate(sensor_points)
    ],
}

with open(OUTPUT_PATH, 'w') as output:
    json.dump(payload, output, separators=(',', ':'))

print(
    "Exported {} vertices, {} faces, and {} sensors to {}".format(
        payload["metadata"]["vertexCount"],
        payload["metadata"]["faceCount"],
        payload["metadata"]["sensorCount"],
        OUTPUT_PATH,
    )
)
