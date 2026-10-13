# Checks the person tracker against a walk we made up, so the right answer is
# known at every step. No lidar needed.
#
# Run with: python3 tests/test_tracker.py

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

import tracker as T

fails = 0
def check(name, cond, detail=""):
    global fails
    fails += 0 if cond else 1
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if detail else ""))

def blob(centre, radius=0.03, n=10):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    pts = np.column_stack((np.cos(a), np.sin(a))) * radius + np.asarray(centre, dtype=float)
    return T.Blob(pts)

def walk(step_t=0.1, speed=1.0, apart=0.25, seconds=2.0):
    """Someone walking in a straight line, legs either side of the middle."""
    out = []
    t = 0.0
    while t <= seconds:
        middle = np.array([speed * t, 0.0])
        out.append((t, middle, middle + np.array([0.0, apart / 2]),
                    middle - np.array([0.0, apart / 2])))
        t += step_t
    return out

print("--- finding legs in a pile of points ---")
pts = np.vstack([blob((1.0, 0.1)).points, blob((1.0, -0.15)).points])
found = T.find_blobs(pts)
check("two legs come out as two blobs", len(found) == 2, f"{found}")
check("a lone speck is ignored", len(T.find_blobs(np.array([[0.0, 0.0], [0.01, 0.0]]))) == 0)
big = np.column_stack((np.linspace(0, 0.8, 40), np.zeros(40)))
check("something furniture-sized is ignored", len(T.find_blobs(big)) == 0)

print("\n--- walking with both legs visible ---")
tr = T.Tracker()
worst = 0.0
for t, middle, left, right in walk():
    tr.update(t, [blob(left), blob(right)])
    if t > 0.5:
        worst = max(worst, float(np.hypot(*(tr.position - middle))))
check("the midpoint follows the walk", worst < 0.12, f"worst {worst*100:.0f} cm behind")
check("it says both legs", tr.state == T.BOTH, tr.state)
check("and it counts as confident", tr.confident)

print("\n--- one leg lifts out of the slice ---")
tr = T.Tracker()
frozen = None
errors = []
for t, middle, left, right in walk(seconds=3.0):
    if t < 1.0:
        tr.update(t, [blob(left), blob(right)])
    else:
        tr.update(t, [blob(left)])          # the right leg has vanished
        if frozen is None:
            frozen = tr.position.copy()
        errors.append(float(np.hypot(*(tr.position - middle))))
check("it keeps moving instead of freezing",
      float(np.hypot(*(tr.position - frozen))) > 1.0,
      f"moved {np.hypot(*(tr.position - frozen))*100:.0f} cm after the leg went")
check("the midpoint stays near the truth on one leg", max(errors[3:]) < 0.12,
      f"worst {max(errors[3:])*100:.0f} cm")
check("it says one leg", tr.state == T.ONE, tr.state)

print("\n--- standing with feet together ---")
tr = T.Tracker()
for t in np.arange(0, 1.0, 0.1):
    tr.update(float(t), [blob((2.0, 1.0), radius=0.13, n=16)])
check("one wide blob is read as both legs", tr.state == T.TOGETHER, tr.state)
check("the midpoint is its middle", float(np.hypot(*(tr.position - np.array([2.0, 1.0])))) < 0.05,
      str(tr.position))

print("\n--- nobody visible at all ---")
tr = T.Tracker()
for t, middle, left, right in walk(seconds=1.0):
    tr.update(t, [blob(left), blob(right)])
last_seen_at = tr.position.copy()
tr.update(1.1, [])
tr.update(1.2, [])
check("a short gap keeps it moving", tr.state == T.PREDICTED, tr.state)
check("  ...in the direction they were going",
      tr.position[0] > last_seen_at[0] + 0.05,
      f"{last_seen_at[0]:.2f} -> {tr.position[0]:.2f} m")
held = tr.position.copy()
for t in (1.5, 1.8):
    tr.update(t, [])
check("a longer gap holds it still", tr.state == T.HELD, tr.state)
check("  ...and it stops drifting", float(np.hypot(*(tr.position - held))) < 0.01)
check("  ...and it is no longer confident", not tr.confident)
tr.update(3.0, [])
check("a long gap gives up", tr.state == T.LOST and tr.position is None, tr.state)

print("\n--- things that should not fool it ---")
tr = T.Tracker()
for t, middle, left, right in walk(seconds=1.0):
    tr.update(t, [blob(left), blob(right), blob((middle[0] + 3.0, 2.0))])
check("a bag across the carpet is ignored",
      float(np.hypot(*(tr.position - np.array([1.0, 0.0])))) < 0.12, str(tr.position))

before = tr.position.copy()
tr.update(1.1, [blob((9.0, 9.0)), blob((9.0, 9.25))])
check("an impossible jump is refused", float(np.hypot(*(tr.position - before))) < 0.2,
      f"{before} -> {tr.position}")

print("\n--- telling a person from the scenery ---")
bg = T.Background()
empty = [(a, 3000.0, 47) for a in np.arange(0, 360, 0.8)]
for _ in range(10):
    bg.add("A", empty)
bg.finish()
check("the background is learned", bg.ready and bg.rotations == 10)
now = [(10.0, 1500.0, 47), (11.0, 1500.0, 47), (200.0, 3000.0, 47), (201.0, 2990.0, 47)]
mask = bg.foreground("A", now)
check("someone standing in front of the scenery shows up", bool(mask[0] and mask[1]))
check("the scenery itself does not", not bool(mask[2] or mask[3]), str(mask))

print()
print("ALL PASS" if fails == 0 else f"{fails} FAILED")
