# Keeping only the readings that land on the carpet.
#
# The two sensors sit at opposite ends of the carpet's diagonal, each looking
# inwards. Two filters, both worked out from where the sensors are, so nothing
# has to be measured and the carpet can be any size:
#
#   the wedge    each sensor only looks in a cone facing the other one.
#                A square corner spans exactly 90 degrees, so anything wider
#                than that is margin for seeing a foot step off the edge.
#
#   the square   two opposite corners fix a square completely: its other two
#                corners sit either side of the middle, square-on to the
#                diagonal. Points outside it (plus a margin) are dropped.
#
# This assumes the carpet really is square. A rectangle isn't fixed by its
# diagonal alone, and would need its side length measured as well.

import math

import numpy as np

MIN_DIAGONAL_M = 0.30     # closer together than this and the square is meaningless
EDGE_SLACK = 1e-9         # so a point exactly on a boundary counts as inside


def wedge_mask(points, sensor_xy, facing_xy, fov_deg):
    """Which points lie in the cone at `sensor_xy` of width `fov_deg`, pointed
    at `facing_xy`. points is an Nx2 array of metres."""
    points = np.asarray(points, dtype=float)
    if not len(points):
        return np.zeros(0, dtype=bool)

    look = np.asarray(facing_xy, dtype=float) - np.asarray(sensor_xy, dtype=float)
    length = math.hypot(*look)
    if length < 1e-9:
        return np.ones(len(points), dtype=bool)
    look /= length

    rel = points - np.asarray(sensor_xy, dtype=float)
    dist = np.hypot(rel[:, 0], rel[:, 1])
    # a reading at the sensor itself has no direction, so count it as inside
    cosine = np.where(dist > EDGE_SLACK, (rel @ look) / np.maximum(dist, EDGE_SLACK), 1.0)
    return cosine >= math.cos(math.radians(fov_deg / 2.0)) - EDGE_SLACK


def square_from_diagonal(corner_a, corner_b):
    """The four corners of the square whose diagonal runs a to b, starting at a
    and going round. None if the two points are basically on top of each other."""
    a = np.asarray(corner_a, dtype=float)
    b = np.asarray(corner_b, dtype=float)
    half = (b - a) / 2.0
    if math.hypot(*half) * 2 < MIN_DIAGONAL_M:
        return None
    middle = (a + b) / 2.0
    across = np.array([-half[1], half[0]])        # square-on to the diagonal
    return np.array([a, middle + across, b, middle - across])


def square_side(corners):
    return float(np.hypot(*(corners[1] - corners[0])))


def inside_square(points, corners, margin_m=0.0):
    """Which points sit inside the square, allowing a margin outside it."""
    points = np.asarray(points, dtype=float)
    if not len(points):
        return np.zeros(0, dtype=bool)

    origin = corners[0]
    e1 = corners[1] - origin
    e2 = corners[3] - origin
    side = math.hypot(*e1)
    e1, e2 = e1 / side, e2 / side

    rel = points - origin
    along1, along2 = rel @ e1, rel @ e2
    lo, hi = -margin_m - EDGE_SLACK, side + margin_m + EDGE_SLACK
    return (along1 >= lo) & (along1 <= hi) & (along2 >= lo) & (along2 <= hi)


def carpet_mask(points, sensor_xy, facing_xy, fov_deg, corners=None, margin_m=0.0):
    """Everything together: in the wedge, and on the carpet if we know where
    the carpet is."""
    keep = wedge_mask(points, sensor_xy, facing_xy, fov_deg)
    if corners is not None:
        keep &= inside_square(points, corners, margin_m)
    return keep
