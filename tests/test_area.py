# Checks the carpet filter: the square worked out from the sensors' diagonal,
# and the wedge each sensor looks through.
#
# Run with: python3 tests/test_area.py

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

import area

fails = 0
def check(name, cond, detail=""):
    global fails
    fails += 0 if cond else 1
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if detail else ""))


def carpet(side, turn_deg=0.0, centre=(0.0, 0.0)):
    """A square carpet of the given size, turned any which way. Returns its four
    corners and the two opposite ones the sensors sit on."""
    t = math.radians(turn_deg)
    c, s = math.cos(t), math.sin(t)
    R = np.array([[c, -s], [s, c]])
    half = side / 2.0
    pts = np.array([[-half, -half], [-half, half], [half, half], [half, -half]])
    pts = pts @ R.T + np.asarray(centre)
    return pts, pts[0], pts[2]


print("--- the square is worked out from the two sensors alone ---")
for side in (1.5, 2.5, 4.0):
    for turn in (0.0, 23.0, 67.5, 140.0):
        pts, a, b = carpet(side, turn)
        corners = area.square_from_diagonal(a, b)
        got = area.square_side(corners)
        ok = abs(got - side) < 1e-9 and all(
            min(np.hypot(*(corners - p).T)) < 1e-9 for p in pts)
        if not ok:
            check(f"side {side} m turned {turn} deg", False, f"got side {got:.4f}")
            break
    else:
        continue
    break
else:
    check("any size, any angle: the four corners come out right", True,
          "checked 1.5/2.5/4.0 m at 0/23/67.5/140 deg")

check("sensors too close together: no square",
      area.square_from_diagonal((0, 0), (0.1, 0.1)) is None)

print("\n--- what counts as on the carpet ---")
pts, a, b = carpet(2.5, turn_deg=31.0)
corners = area.square_from_diagonal(a, b)
middle = (np.asarray(a) + np.asarray(b)) / 2
inside = np.array([middle, (a + middle) / 2, (b + middle) / 2])
check("middle and in-between spots are on it", area.inside_square(inside, corners).all())
check("the corners themselves are on it", area.inside_square(pts, corners).all())

far = np.array([middle + np.array([5.0, 0.0]), middle + np.array([0.0, -4.0])])
check("things well off the carpet are dropped", not area.inside_square(far, corners).any())

just_off = np.array([pts[1] + (pts[1] - middle) / np.hypot(*(pts[1] - middle)) * 0.15])
check("15 cm past a corner is off it", not area.inside_square(just_off, corners).any())
check("  ...but a 25 cm margin keeps it", area.inside_square(just_off, corners, 0.25).all())

print("\n--- the wedge each sensor looks through ---")
# from a square's corner, the carpet sits inside exactly 90 degrees
edge = np.linspace(0, 1, 60)
all_of_it = np.vstack([a + (c - a) * edge[:, None] for c in (pts[1], pts[2], pts[3])])
check("90 deg covers the whole carpet from a corner",
      area.wedge_mask(all_of_it, a, b, 90.0 + 1e-6).all())
check("89 deg does not quite",
      not area.wedge_mask(all_of_it, a, b, 89.0).all())
check("145 deg covers it with room to spare",
      area.wedge_mask(all_of_it, a, b, 145.0).all())

behind = np.array([a - (np.asarray(b) - np.asarray(a)) * 0.3])
check("things behind the sensor are dropped", not area.wedge_mask(behind, a, b, 145.0).any())

# 145 deg is 72.5 either side of the diagonal; the carpet edge is 45 deg off it
sideways = []
for off in (44.0, 46.0, 71.0, 74.0):
    t = math.radians(off)
    look = (np.asarray(b) - np.asarray(a))
    look = look / np.hypot(*look)
    turned = np.array([look[0] * math.cos(t) - look[1] * math.sin(t),
                       look[0] * math.sin(t) + look[1] * math.cos(t)])
    sideways.append(np.asarray(a) + turned * 1.0)
got = area.wedge_mask(np.array(sideways), a, b, 145.0)
check("145 deg lets in 71 deg off the diagonal but not 74", list(got) == [True, True, True, False],
      f"{list(got)} at 44/46/71/74 deg")

print("\n--- the two together ---")
off_carpet_but_in_wedge = np.array([middle + (np.asarray(b) - np.asarray(a)) * 1.5])
check("in the wedge but past the carpet: wedge alone keeps it",
      area.carpet_mask(off_carpet_but_in_wedge, a, b, 145.0).all())
check("  ...and the square crop drops it",
      not area.carpet_mask(off_carpet_but_in_wedge, a, b, 145.0, corners).any())
check("a spot on the carpet survives both",
      area.carpet_mask(np.array([middle]), a, b, 145.0, corners).all())

print()
print("ALL PASS" if fails == 0 else f"{fails} FAILED")
