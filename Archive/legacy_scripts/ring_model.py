"""Grasshopper Python component script for the 30-sensor Ring layout.

GhPython inputs:
    Diameter: ring diameter in mm, default 17
    Gap: distance between the two ring center planes in mm, default 27
    Nodes: nodes on each ring, default 10

Outputs:
    RingMesh, SensorPoints, ConnectingLines, LeftPoints, MiddlePoints, RightPoints

Sensor order is always:
    0..9   left ring
    10..19 middle points on the ten connecting lines
    20..29 right ring
"""

import math
import Rhino.Geometry as rg


def value_or_default(value, default):
    try:
        return float(value) if value is not None else default
    except Exception:
        return default


diameter = value_or_default(Diameter, 17.0)
gap = value_or_default(Gap, 27.0)
nodes = max(3, int(value_or_default(Nodes, 10)))
radius = diameter / 2.0


def ring_points(x):
    result = []
    for index in range(nodes):
        angle = (2.0 * math.pi * index) / nodes
        result.append(rg.Point3d(x, radius * math.cos(angle), radius * math.sin(angle)))
    return result


left = ring_points(-gap / 2.0)
right = ring_points(gap / 2.0)
middle = []
lines = []

for index in range(nodes):
    line = rg.Line(left[index], right[index])
    lines.append(rg.LineCurve(line))
    middle.append(line.PointAt(0.5))

all_sensors = left + middle + right

# A simple open cylindrical mesh connecting the two circular boundaries.
mesh = rg.Mesh()
for point in left + right:
    mesh.Vertices.Add(point)

for index in range(nodes):
    next_index = (index + 1) % nodes
    mesh.Faces.AddFace(index, next_index, nodes + next_index, nodes + index)

mesh.Normals.ComputeNormals()
mesh.Compact()

RingMesh = mesh
SensorPoints = all_sensors
ConnectingLines = lines
LeftPoints = left
MiddlePoints = middle
RightPoints = right
