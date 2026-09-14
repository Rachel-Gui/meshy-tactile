import math
import Rhino.Geometry as rg
from System.Drawing import Color

ROWS = 12
COLUMNS = 8
SENSOR_COUNT = 96


def clamp01(value):
    return max(0.0, min(1.0, float(value)))


def heat_color(value):
    value = clamp01(value)

    color_stops = (
        (0.00, (20, 30, 110)),
        (0.25, (0, 170, 255)),
        (0.50, (30, 220, 120)),
        (0.75, (255, 220, 0)),
        (1.00, (230, 30, 20)),
    )

    for index in range(len(color_stops) - 1):
        start_t, start_color = color_stops[index]
        end_t, end_color = color_stops[index + 1]

        if value <= end_t:
            amount = (value - start_t) / (end_t - start_t)

            rgb = tuple(
                int(round(start + (end - start) * amount))
                for start, end in zip(start_color, end_color)
            )

            return Color.FromArgb(*rgb)

    return Color.FromArgb(*color_stops[-1][1])


def convert_to_brep(geometry):
    if isinstance(geometry, rg.Brep):
        return geometry

    if isinstance(geometry, rg.BrepFace):
        return geometry.DuplicateFace(False)

    if isinstance(geometry, rg.Surface):
        return geometry.ToBrep()

    return None


def order_sensor_points(points):
    points = list(points)

    if len(points) != SENSOR_COUNT:
        raise ValueError(
            "Points must contain exactly 96 intersections. "
            "Received {}.".format(len(points))
        )

    bounding_box = rg.BoundingBox(points)
    tolerance = max(
        0.001,
        bounding_box.Diagonal.Length * 0.0001
    )

    points_by_x = sorted(points, key=lambda point: point.X)
    columns = []

    for point in points_by_x:
        if not columns:
            columns.append([point])
            continue

        average_x = (
            sum(item.X for item in columns[-1])
            / len(columns[-1])
        )

        if abs(point.X - average_x) <= tolerance:
            columns[-1].append(point)
        else:
            columns.append([point])

    if len(columns) != COLUMNS:
        raise ValueError(
            "Expected 8 sensor columns. Found {}.".format(
                len(columns)
            )
        )

    for index, column in enumerate(columns):
        if len(column) != ROWS:
            raise ValueError(
                "Column {} contains {} points instead of 12.".format(
                    index + 1,
                    len(column)
                )
            )

        column.sort(
            key=lambda point: math.atan2(point.Z, point.Y)
        )

    return [
        columns[column][row]
        for row in range(ROWS)
        for column in range(COLUMNS)
    ]


def order_sensor_values(values):
    values = [clamp01(value) for value in values]

    if len(values) != SENSOR_COUNT:
        raise ValueError(
            "Values must contain exactly 96 numbers. "
            "Received {}.".format(len(values))
        )

    rotation = int(Rotate or 0) % ROWS
    flip_rows = bool(FlipU)
    flip_columns = bool(FlipV)

    ordered_values = []

    for row in range(ROWS):
        source_row = (row + rotation) % ROWS

        if flip_rows:
            source_row = ROWS - 1 - source_row

        for column in range(COLUMNS):
            source_column = (
                COLUMNS - 1 - column
                if flip_columns
                else column
            )

            source_index = (
                source_row * COLUMNS
                + source_column
            )

            ordered_values.append(values[source_index])

    return ordered_values


def calculate_field_value(
    vertex,
    sensor_points,
    sensor_values,
    radius
):
    strongest_value = 0.0

    for sensor_point, sensor_value in zip(
        sensor_points,
        sensor_values
    ):
        distance = vertex.DistanceTo(sensor_point)

        if distance >= radius:
            continue

        amount = 1.0 - distance / radius

        # Smooth falloff from the sensor center to the edge.
        falloff = amount * amount * (3.0 - 2.0 * amount)
        influence = sensor_value * falloff

        if influence > strongest_value:
            strongest_value = influence

    return clamp01(strongest_value)


try:
    if Strips is None:
        raise ValueError("Strips input is empty.")

    if Points is None:
        raise ValueError("Points input is empty.")

    if Values is None:
        raise ValueError("Values input is empty.")

    sensor_points = order_sensor_points(Points)
    sensor_values = order_sensor_values(Values)

    heat_radius = max(
        0.1,
        float(Radius if Radius is not None else 25.0)
    )

    mesh_edge_size = max(
        0.1,
        float(MeshSize if MeshSize is not None else 3.0)
    )

    preview_offset = float(
        Offset if Offset is not None else 0.0
    )

    meshing_parameters = rg.MeshingParameters()
    meshing_parameters.MaximumEdgeLength = mesh_edge_size
    meshing_parameters.MinimumEdgeLength = mesh_edge_size * 0.25
    meshing_parameters.RefineGrid = True
    meshing_parameters.JaggedSeams = False
    meshing_parameters.SimplePlanes = False

    heat_mesh = rg.Mesh()
    mesh_piece_count = 0

    for geometry in Strips:
        brep = convert_to_brep(geometry)

        if brep is None:
            continue

        mesh_pieces = rg.Mesh.CreateFromBrep(
            brep,
            meshing_parameters
        )

        if not mesh_pieces:
            continue

        for mesh in mesh_pieces:
            if mesh is None or mesh.Vertices.Count == 0:
                continue

            mesh.Normals.ComputeNormals()
            mesh.VertexColors.CreateMonotoneMesh(
                Color.FromArgb(20, 30, 110)
            )

            for vertex_index in range(mesh.Vertices.Count):
                vertex = rg.Point3d(
                    mesh.Vertices[vertex_index]
                )

                field_value = calculate_field_value(
                    vertex,
                    sensor_points,
                    sensor_values,
                    heat_radius
                )

                mesh.VertexColors.SetColor(
                    vertex_index,
                    heat_color(field_value)
                )

                if abs(preview_offset) > 0.000001:
                    normal = rg.Vector3d(
                        mesh.Normals[vertex_index]
                    )

                    moved_vertex = (
                        vertex
                        + normal * preview_offset
                    )

                    mesh.Vertices.SetVertex(
                        vertex_index,
                        moved_vertex.X,
                        moved_vertex.Y,
                        moved_vertex.Z
                    )

            mesh.Normals.ComputeNormals()
            heat_mesh.Append(mesh)
            mesh_piece_count += 1

    heat_mesh.Compact()

    if heat_mesh.Vertices.Count == 0:
        raise ValueError(
            "No mesh could be generated from the strip surfaces."
        )

    # The actual Grasshopper output variable is named "out".
    HeatMesh = heat_mesh

    Status = (
        "OK - strip heatmap | "
        "{} sensor points | "
        "{} mesh pieces | "
        "{} vertices"
    ).format(
        len(sensor_points),
        mesh_piece_count,
        heat_mesh.Vertices.Count
    )

except Exception as error:
    HeatMesh = None
    Status = "ERROR - {}".format(error)