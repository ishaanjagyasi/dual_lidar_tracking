# Lining two lidars up automatically, by matching the shapes they both see.
#
# Both sensors see the same walls, just from different places. This slides and
# turns one sensor's points until they sit on top of the other's. The method is
# ICP (iterative closest point):
#
#   1. start from a rough guess of where the sensor is
#   2. pair every point with the nearest point from the other sensor
#   3. work out the one slide-and-turn that shrinks all those gaps the most
#   4. apply it and repeat until it stops improving
#
# Step 3 measures the gap to the *wall the other point sits on*, not to that
# point itself. The two sensors never sample the same spots on a wall, so
# pulling point onto point drags the answer along the wall by about half the
# spacing between readings - a few centimetres at 3 m.
#
# It only ever looks at *nearest* points, so a bad starting guess can pair
# points with the wrong wall and settle there, confidently wrong. Two guards:
# several starting guesses are tried and the best kept, and the answer is
# poked afterwards to see whether the room shape really pins it down (a bare
# corridor does not - sliding along a wall looks just as good).

import math

import numpy as np
from scipy.spatial import cKDTree

MAX_PAIR_M = 0.30       # a point further than this from anything is not a match
MIN_PAIRS = 60          # fewer matched points than this means it can't be trusted
ITERATIONS = 40
TOL_M = 1e-4
TOL_DEG = 1e-3
TRY_TURNS = (0.0, -30.0, -15.0, 15.0, 30.0)   # extra starting guesses, degrees
MAX_POINTS = 4000       # thin out bigger clouds; it doesn't need them
GOOD_GAP_M = 0.05       # an average gap under this is a good match
NUDGE_M = 0.10          # how far to poke the answer when testing it
NUDGE_DEG = 2.0
WEAK_RATIO = 1.25       # if a poke barely worsens the gap, the shape is too plain


def polar_to_local(points):
    """[(angle_deg, dist_mm, quality)] -> Nx2 metres in the sensor's own frame."""
    if not len(points):
        return np.zeros((0, 2))
    a = np.radians(np.fromiter((p[0] for p in points), float, len(points)))
    d = np.fromiter((p[1] for p in points), float, len(points)) / 1000.0
    return np.column_stack((d * np.sin(a), d * np.cos(a)))


def transform(local, x, y, turn_deg):
    """Put a sensor's own points on the shared map (matches Sensor.to_world)."""
    t = math.radians(turn_deg)
    c, s = math.cos(t), math.sin(t)
    out = np.empty_like(local)
    out[:, 0] = local[:, 0] * c + local[:, 1] * s + x
    out[:, 1] = -local[:, 0] * s + local[:, 1] * c + y
    return out


def _thin(pts):
    if len(pts) <= MAX_POINTS:
        return pts
    return pts[:: int(np.ceil(len(pts) / MAX_POINTS))]


def wall_directions(target, tree, k=6):
    """For each point, which way the surface it sits on runs. Returned as the
    direction across that surface (its normal), from the few nearest points."""
    k = min(k, len(target))
    if k < 3:
        return None
    _d, idx = tree.query(target, k=k)
    nb = target[idx]
    nb = nb - nb.mean(axis=1, keepdims=True)
    cov = np.einsum("nki,nkj->nij", nb, nb) / k
    _w, v = np.linalg.eigh(cov)
    return v[:, :, 0]          # the direction things vary in least: across the wall


def _gap(local, tree, pose):
    """Average distance from each moved point to the nearest point of the other
    sensor, and how many points found one at all."""
    dist, _idx = tree.query(transform(local, *pose), distance_upper_bound=MAX_PAIR_M)
    ok = np.isfinite(dist)
    if not ok.any():
        return float("inf"), 0
    return float(dist[ok].mean()), int(ok.sum())


def icp(local, tree, target, normals, guess, iterations=ITERATIONS):
    x, y, turn = guess
    for _ in range(iterations):
        moved = transform(local, x, y, turn)
        dist, idx = tree.query(moved, distance_upper_bound=MAX_PAIR_M)
        ok = np.isfinite(dist)
        if int(ok.sum()) < MIN_PAIRS:
            break
        p, q, n = moved[ok], target[idx[ok]], normals[idx[ok]]

        # how far each point sits off the wall it was matched to
        off = np.einsum("ij,ij->i", n, p - q)
        limit = 2.5 * np.median(np.abs(off)) + 1e-6
        keep = np.abs(off) <= limit
        if int(keep.sum()) >= MIN_PAIRS:
            p, n, off = p[keep], n[keep], off[keep]

        # solve for the small turn and slide that flattens all those offsets
        turn_term = n[:, 1] * p[:, 0] - n[:, 0] * p[:, 1]
        A = np.column_stack((turn_term, n[:, 0], n[:, 1]))
        step, *_ = np.linalg.lstsq(A, -off, rcond=None)
        th = float(np.clip(step[0], -0.2, 0.2))
        tx, ty = float(step[1]), float(step[2])

        c, sn = math.cos(th), math.sin(th)
        pos = np.array([[c, -sn], [sn, c]]) @ np.array([x, y]) + np.array([tx, ty])
        x, y, turn = float(pos[0]), float(pos[1]), turn - math.degrees(th)
        if abs(math.degrees(th)) < TOL_DEG and math.hypot(tx, ty) < TOL_M:
            break
    gap, pairs = _gap(local, tree, (x, y, turn))
    return (x, y, turn), gap, pairs


def wall_gap(local, tree, target, normals, pose):
    """Average distance from each point to the wall it was matched to. This is
    the real measure of the alignment: the plain point-to-point gap is mostly
    the spacing between readings, since the sensors never sample the same spots."""
    moved = transform(local, *pose)
    dist, idx = tree.query(moved, distance_upper_bound=MAX_PAIR_M)
    ok = np.isfinite(dist)
    if not ok.any():
        return float("inf")
    off = np.einsum("ij,ij->i", normals[idx[ok]], moved[ok] - target[idx[ok]])
    return float(np.abs(off).mean())


def _pins_it_down(local, tree, pose, gap):
    """Poke the answer about. If the gap barely grows, the room shape doesn't
    actually fix where the sensor is (e.g. a bare corridor)."""
    if gap <= 0:
        return True, 0.0
    worst = float("inf")
    for dx, dy, dt in ((NUDGE_M, 0, 0), (-NUDGE_M, 0, 0), (0, NUDGE_M, 0),
                       (0, -NUDGE_M, 0), (0, 0, NUDGE_DEG), (0, 0, -NUDGE_DEG)):
        poked, _n = _gap(local, tree, (pose[0] + dx, pose[1] + dy, pose[2] + dt))
        worst = min(worst, poked / gap)
    return worst >= WEAK_RATIO, worst


def calibrate(source_points, target_world, guess):
    """Line one sensor up with another's points.

    source_points : that sensor's own readings, [(angle_deg, dist_mm, quality)]
    target_world  : the other sensor's points on the shared map, Nx2 metres
    guess         : (x, y, turn_deg) roughly where the sensor is

    Returns (pose, report) where pose is None if it could not be trusted.
    """
    local = _thin(polar_to_local(source_points))
    target = _thin(np.asarray(target_world, dtype=float))
    if len(local) < MIN_PAIRS or len(target) < MIN_PAIRS:
        return None, "not enough points yet - let both sensors spin a moment"

    tree = cKDTree(target)
    normals = wall_directions(target, tree)
    if normals is None:
        return None, "not enough points yet - let both sensors spin a moment"

    best = None
    for extra in TRY_TURNS:
        pose, gap, pairs = icp(local, tree, target, normals,
                               (guess[0], guess[1], guess[2] + extra))
        if best is None or gap < best[1]:
            best = (pose, gap, pairs)

    pose, gap, pairs = best
    if pairs < MIN_PAIRS:
        return None, f"only {pairs} points matched - move it closer by hand first"

    if gap > GOOD_GAP_M:
        return None, (f"poor match ({gap*1000:.0f} mm average gap) - "
                      "line it up closer by hand, then try again")

    firm, _ratio = _pins_it_down(local, tree, pose, gap)
    off_mm = wall_gap(local, tree, target, normals, pose) * 1000
    if not firm:
        return pose, (f"matched to {off_mm:.0f} mm off the walls, but the shape here "
                      "is too plain to be sure - check it by eye")
    return pose, f"aligned: {off_mm:.0f} mm off the walls, {pairs} points matched"
