# The carpet, cut into the game's grid, and spoken in the game's units.
#
# The Processing sketch (gridGameWinter) knows nothing about lidars. It listens
# on UDP 6800 for "/position x y" - two floats, millimetres - and turns them
# into a tile like this (OSCReceiveClass.pde):
#
#     col = floor( x / 1000 / tileLength)
#     row = floor(-y / 1000 / tileLength)          tileLength = 0.5 m
#
# So rather than change the sketch, this does the fitting on our side. The two
# sensors stand on opposite corners of the carpet, which pins down the whole
# square. Any point on it can then be expressed as "this far along the columns,
# this far down the rows", in tiles, and sent as the millimetres that make the
# sketch's own arithmetic land on that tile - whatever size the carpet really
# is. A 1.1 m carpet and a 2.5 m one both fill the same 5 x 5 grid.
#
# Stepping off the carpet gives a row or column outside the grid, and the sketch
# treats that as a game event (a bell opportunity), so it must arrive as it is.
# The one exception is a thin band along the edge, `edge_m` wide: a reading
# that lands just past the edge is pulled back onto the edge tile. The C1 is
# only good to about 3 cm and the tracker to 4-7 cm, so "2 cm off the carpet"
# is not something the sensors can actually tell apart from "on it" - and on a
# small carpet, walking down the middle of an edge tile keeps you barely a
# hand's width from the edge, where an overshoot on a turn rang false bells.
#
# Which corner is tile (0, 0), and which edge the columns run along, cannot be
# known from the sensors - it depends where the screen is. So it is a setting:
# `rotation` walks the origin round the four corners, `mirror` swaps rows and
# columns. Set it once by standing in a corner and watching the sketch.

import json
import math
import os

import numpy as np

import area

SKETCH_TILE_MM = 500.0      # tileLength in OSCReceiveClass.pde, in mm


class CarpetGrid:
    def __init__(self, corners, rows=5, cols=5, rotation=0, mirror=False):
        """corners: the four carpet corners going round, as area.square_from_diagonal
        returns them - starting at sensor A, with sensor B opposite."""
        self.corners = np.asarray(corners, dtype=float)
        self.rows, self.cols = int(rows), int(cols)
        self.rotation = int(rotation) % 4
        self.mirror = bool(mirror)

        i = self.rotation
        self.origin = self.corners[i]
        nxt = self.corners[(i + 1) % 4] - self.origin
        prv = self.corners[(i - 1) % 4] - self.origin
        self.col_edge, self.row_edge = (prv, nxt) if self.mirror else (nxt, prv)

    @property
    def side(self):
        return float(np.hypot(*self.col_edge))

    @property
    def tile_m(self):
        return self.side / self.cols

    def to_grid(self, point, edge_m=0.0):
        """A point on the floor, in metres, to (col, row) in tiles. Continuous and
        unclamped: 2.5 is the middle of the third tile, -0.3 is off the edge.

        edge_m: a reading less than this far past the edge is put back on the
        edge tile, because it is closer than the sensors can tell apart.
        """
        v = np.asarray(point, dtype=float) - self.origin
        col = float(v @ self.col_edge) / float(self.col_edge @ self.col_edge) * self.cols
        row = float(v @ self.row_edge) / float(self.row_edge @ self.row_edge) * self.rows
        if edge_m > 0:
            band = edge_m / self.tile_m
            col = _pull_in(col, self.cols, band)
            row = _pull_in(row, self.rows, band)
        return col, row

    def tile(self, point):
        """Which tile, as the sketch will see it: (row, col) integers, which may be
        outside the grid. Same flooring as the sketch."""
        col, row = self.to_grid(point)
        return int(math.floor(row)), int(math.floor(col))

    def inside(self, row, col):
        return 0 <= row < self.rows and 0 <= col < self.cols

    def to_floor(self, col, row):
        """The other way: tile coordinates back to a point on the floor."""
        return (self.origin + self.col_edge * (col / self.cols)
                + self.row_edge * (row / self.rows))

    def cell(self, row, col):
        """The four floor corners of one tile, for drawing."""
        return np.array([self.to_floor(col, row), self.to_floor(col + 1, row),
                         self.to_floor(col + 1, row + 1), self.to_floor(col, row + 1)])


def _pull_in(value, size, band):
    """Back onto the grid if it is only just off it."""
    if -band < value < 0:
        return 0.0
    if size <= value < size + band:
        return size - 1e-6
    return value


def to_sketch_mm(col, row, tile_mm=SKETCH_TILE_MM):
    """Tile coordinates to the millimetres that make the sketch's own arithmetic
    land on that tile. The sketch negates y, so this does too."""
    return float(col * tile_mm), float(-row * tile_mm)


def sketch_tile(x_mm, y_mm, tile_m=SKETCH_TILE_MM / 1000.0):
    """Exactly what OSCReceiveClass.pde does with a /position message, so that
    the round trip can be checked here without running Processing."""
    pos_x = (x_mm / 1000.0) / tile_m
    pos_y = -((y_mm / 1000.0) / tile_m)
    return int(math.floor(pos_y)), int(math.floor(pos_x))     # (row, col)


def from_sensors(sensor_a_xy, sensor_b_xy, **kw):
    corners = area.square_from_diagonal(sensor_a_xy, sensor_b_xy)
    return None if corners is None else CarpetGrid(corners, **kw)


def load_setting(path):
    try:
        d = json.load(open(path))
        return int(d.get("rotation", 0)) % 4, bool(d.get("mirror", False))
    except Exception:
        return 0, False


def save_setting(path, rotation, mirror):
    with open(path, "w") as fh:
        json.dump({"rotation": int(rotation) % 4, "mirror": bool(mirror)}, fh, indent=2)
