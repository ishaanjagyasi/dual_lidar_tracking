# Checks the automatic alignment against answers we already know.
#
# Builds a fake room, works out what each of two lidars would see from a known
# pair of spots, then asks align.calibrate() to recover the spacing between
# them. Run with: python3 tests/test_align.py

import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

import align

fails = 0
def check(name, cond, detail=""):
    global fails
    fails += 0 if cond else 1
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if detail else ""))

def walls_room():
    """A 5 x 4 m room with a box in it, so there are plenty of corners.
    Coordinates are relative to sensor A, which stands inside at (0, 0)."""
    r = [((-1,-1),(4,-1)), ((4,-1),(4,3)), ((4,3),(-1,3)), ((-1,3),(-1,-1))]
    b = [((1.2,0.2),(2.0,0.2)), ((2.0,0.2),(2.0,1.0)), ((2.0,1.0),(1.2,1.0)), ((1.2,1.0),(1.2,0.2))]
    return r + b

def walls_corridor():
    """Two long parallel walls and nothing else: nothing fixes where you are
    along them."""
    return [((-10,-0.6),(10,-0.6)), ((-10,1.6),(10,1.6))]

def cast(walls, pos, turn_deg, step_deg=0.8, noise_m=0.0, seed=0, max_m=12.0):
    """What a lidar at this spot would report: [(angle_deg, dist_mm, quality)]."""
    rng = random.Random(seed)
    out = []
    a = 0.0
    while a < 360.0:
        th = math.radians(a + turn_deg)
        dx, dy = math.sin(th), math.cos(th)
        best = None
        for (x1,y1),(x2,y2) in walls:
            ex, ey = x2-x1, y2-y1
            den = dx*ey - dy*ex
            if abs(den) < 1e-12:
                continue
            t = ((x1-pos[0])*ey - (y1-pos[1])*ex) / den
            u = ((x1-pos[0])*dy - (y1-pos[1])*dx) / den
            if t > 0.05 and 0.0 <= u <= 1.0 and t < max_m and (best is None or t < best):
                best = t
        if best is not None:
            d = best + (rng.gauss(0, noise_m) if noise_m else 0.0)
            out.append((a, d*1000.0, 47))
        a += step_deg
    return out

TRUE = (2.6, 1.9, 137.0)

def run(walls, guess, noise=0.0, seed=1, true=TRUE):
    a_pts = cast(walls, (0.0, 0.0), 0.0, noise_m=noise, seed=seed)
    b_pts = cast(walls, (true[0], true[1]), true[2], noise_m=noise, seed=seed+99)
    a_world = align.polar_to_local(a_pts)          # sensor A is the origin
    return align.calibrate(b_pts, a_world, guess), len(a_pts), len(b_pts)

print("--- a normal room ---")
(pose, msg), na, nb = run(walls_room(), guess=(2.35, 2.10, 127.0))
print(f"   A saw {na} points, B saw {nb};  {msg}")
check("recovers the position", pose is not None and math.dist(pose[:2], TRUE[:2]) < 0.02,
      "none" if pose is None else f"off by {math.dist(pose[:2], TRUE[:2])*1000:.0f} mm")
check("recovers the turn", pose is not None and abs(pose[2] - TRUE[2]) < 0.5,
      "none" if pose is None else f"{pose[2]:.2f} deg vs {TRUE[2]}")

print("\n--- same room, 10 mm of noise on every reading ---")
(pose, msg), _na, _nb = run(walls_room(), guess=(2.35, 2.10, 127.0), noise=0.010)
print(f"   {msg}")
check("still finds it with noise", pose is not None and math.dist(pose[:2], TRUE[:2]) < 0.03,
      "none" if pose is None else f"off by {math.dist(pose[:2], TRUE[:2])*1000:.0f} mm, turn {pose[2]:.2f}")

print("\n--- a rough guess, 35 degrees out ---")
(pose, msg), _na, _nb = run(walls_room(), guess=(2.2, 2.3, 102.0))
print(f"   {msg}")
check("the extra starting guesses rescue it", pose is not None and math.dist(pose[:2], TRUE[:2]) < 0.05,
      "none" if pose is None else f"off by {math.dist(pose[:2], TRUE[:2])*1000:.0f} mm, turn {pose[2]:.2f}")

print("\n--- a hopeless guess, 90 degrees out ---")
(pose, msg), _na, _nb = run(walls_room(), guess=(2.2, 2.3, 47.0))
ok = pose is None or math.dist(pose[:2], TRUE[:2]) < 0.05
print(f"   {msg}")
check("either finds it or says so - never silently wrong", ok,
      "none" if pose is None else f"off by {math.dist(pose[:2], TRUE[:2])*1000:.0f} mm")

print("\n--- a bare corridor: two parallel walls, nothing else ---")
true_c = (3.0, 1.1, 180.0)
(pose, msg), _na, _nb = run(walls_corridor(), guess=(2.7, 1.1, 172.0), true=true_c)
print(f"   {msg}")
check("warns that the shape can't pin it down", pose is None or "too plain" in msg, msg)

print("\n--- not enough points ---")
(pose, msg), _na, _nb = (align.calibrate([(0, 1000, 40)] * 5, np.zeros((5, 2)), (0, 0, 0)), 0, 0)
print(f"   {msg}")
check("says so instead of guessing", pose is None and "not enough" in msg)

print()
print("ALL PASS" if fails == 0 else f"{fails} FAILED")
