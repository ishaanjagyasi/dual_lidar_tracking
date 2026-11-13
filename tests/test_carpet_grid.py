# The carpet cut into the game's 5x5 grid, checked against the sketch's own
# arithmetic. sketch_tile() is a line-for-line copy of what
# OSCReceiveClass.pde does with a /position message, so if a point here comes
# back as the right tile, it will in Processing too.
#
#   python3 tests/test_carpet_grid.py

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import carpet_grid as cg

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ok    {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


def round_trip(grid):
    """Every tile centre, through to_grid -> mm -> the sketch's maths."""
    wrong = []
    for row in range(grid.rows):
        for col in range(grid.cols):
            centre = grid.to_floor(col + 0.5, row + 0.5)
            x, y = cg.to_sketch_mm(*grid.to_grid(centre))
            got = cg.sketch_tile(x, y)
            if got != (row, col):
                wrong.append(((row, col), got))
    return wrong


def test_your_carpet():
    print("\nthe carpet as calibrated: A at the origin, B at (-0.074, +1.544)")
    grid = cg.from_sensors((0.0, 0.0), (-0.074, 1.544))
    check("a square comes out", grid is not None)
    print(f"    side {grid.side:.3f} m, so each of the 25 tiles is "
          f"{grid.tile_m*100:.1f} cm")
    check("side is the diagonal over root 2",
          abs(grid.side - math.hypot(-0.074, 1.544) / math.sqrt(2)) < 1e-9)
    wrong = round_trip(grid)
    check("all 25 tiles land where the sketch will put them", not wrong, str(wrong[:3]))
    check("sensor A's corner is tile (0, 0)",
          cg.sketch_tile(*cg.to_sketch_mm(*grid.to_grid(
              grid.to_floor(0.05, 0.05)))) == (0, 0))
    check("sensor B's corner is the far tile (4, 4)",
          grid.tile(grid.to_floor(4.95, 4.95)) == (4, 4))


def test_other_sizes_and_angles():
    print("\nany size, any angle: a 2.5 m carpet turned 37 degrees, and a tiny one")
    for a, b in (((1.0, -2.0), (1.0 + 2.5 * math.cos(math.radians(37 + 45)) * math.sqrt(2),
                                -2.0 + 2.5 * math.sin(math.radians(37 + 45)) * math.sqrt(2))),
                 ((0.0, 0.0), (0.4, 0.4))):
        grid = cg.from_sensors(a, b)
        wrong = round_trip(grid)
        check(f"{grid.side:.2f} m carpet: all 25 tiles right", not wrong, str(wrong[:3]))


def test_rotation_and_mirror():
    print("\nall eight ways the grid can sit on the carpet")
    seen_origins = set()
    for rotation in range(4):
        for mirror in (False, True):
            grid = cg.from_sensors((0.0, 0.0), (-0.074, 1.544),
                                   rotation=rotation, mirror=mirror)
            wrong = round_trip(grid)
            check(f"rotation {rotation} mirror {mirror!s:5}: every tile round-trips",
                  not wrong, str(wrong[:3]))
            seen_origins.add((round(grid.origin[0], 6), round(grid.origin[1], 6)))
    check("rotation walks tile (0,0) round all four corners", len(seen_origins) == 4,
          str(seen_origins))

    plain = cg.from_sensors((0, 0), (0, 2), rotation=0, mirror=False)
    flipped = cg.from_sensors((0, 0), (0, 2), rotation=0, mirror=True)
    p = plain.to_floor(1.5, 3.5)                     # col 1, row 3
    check("mirror swaps rows and columns", flipped.tile(p) == (1, 3),
          f"{flipped.tile(p)}")


def test_off_the_carpet():
    print("\nstepping off - must NOT be clamped, the sketch scores it")
    grid = cg.from_sensors((0.0, 0.0), (-0.074, 1.544))
    for col, row, label in ((-0.4, 2.5, "off the left"), (5.3, 2.5, "off the right"),
                            (2.5, -0.2, "off the top"), (2.5, 5.6, "off the bottom")):
        x, y = cg.to_sketch_mm(*grid.to_grid(grid.to_floor(col, row)))
        r, c = cg.sketch_tile(x, y)
        check(f"{label}: arrives as ({r}, {c}), outside the grid",
              not (0 <= r < 5 and 0 <= c < 5))


def test_edge_band():
    print("\nthe edge band: just past the edge is still on, clearly past is off")
    grid = cg.from_sensors((0.0, 0.0), (-0.074, 1.544))
    t = grid.tile_m
    for over, expect_on in ((0.02, True), (0.045, True), (0.08, False), (0.30, False)):
        for col, row, label in ((-over / t, 2.5, "left"), (5 + over / t, 2.5, "right"),
                                (2.5, -over / t, "top"), (2.5, 5 + over / t, "bottom")):
            p = grid.to_floor(col, row)
            r, c = cg.sketch_tile(*cg.to_sketch_mm(*grid.to_grid(p, edge_m=0.05)))
            on = grid.inside(r, c)
            if on != expect_on:
                check(f"{over*100:.1f} cm off the {label}", False,
                      f"came out ({r},{c})")
                break
        else:
            check(f"{over*100:.1f} cm past any edge is {'ON' if expect_on else 'OFF'} "
                  f"the grid", True)
    inside = grid.to_floor(2.3, 3.7)
    check("points on the carpet are untouched",
          grid.to_grid(inside, 0.05) == grid.to_grid(inside))
    off = grid.to_floor(-0.1, 2.5)
    check("edge 0 switches it off", grid.tile(off)[1] < 0
          and grid.to_grid(off, 0.0) == grid.to_grid(off))


def test_messages_are_floats():
    print("\nthe sketch only accepts /position with typetag ff")
    x, y = cg.to_sketch_mm(2, 3)
    check("both values are floats", isinstance(x, float) and isinstance(y, float),
          f"{type(x)} {type(y)}")


def test_setting_is_remembered():
    print("\nthe chosen orientation survives a restart")
    import tempfile
    path = os.path.join(tempfile.mkdtemp(), "carpet_grid.json")
    check("nothing saved yet means the default", cg.load_setting(path) == (0, False))
    cg.save_setting(path, 3, True)
    check("comes back as saved", cg.load_setting(path) == (3, True))


if __name__ == "__main__":
    test_your_carpet()
    test_other_sizes_and_angles()
    test_rotation_and_mirror()
    test_off_the_carpet()
    test_edge_band()
    test_messages_are_floats()
    test_setting_is_remembered()
    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
