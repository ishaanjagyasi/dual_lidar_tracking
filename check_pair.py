# Before calibrating: can these two sensors actually see each other?
#
#   python3 check_pair.py
#
# calibrate_pair.py tells you when it fails, but not always why, because by
# then it is reasoning about marker pairings. This looks further back and
# answers the two questions underneath:
#
#   is each jig on, and on the right way round?
#       Every sensor should see its OWN two posts at about 65 mm - the post
#       centres are 80 mm out and the laser stops at the near face. If those
#       are missing the jig is not seated.
#
#   are both sensors in the same space at all?
#       Two scans of one room can be laid on top of each other; two scans of
#       different rooms, or of a room split by a wall or a sofa, cannot. This
#       searches every plausible place and heading for the second sensor and
#       reports the best fit it can find. A real one is a few millimetres off
#       the walls with most of the scan matched. Anything else means no amount
#       of turning the jigs will help - they are not looking at the same place.
#
# Nothing here is written to disk and no alignment is saved.

import argparse
import math
import sys

import numpy as np
from scipy.spatial import cKDTree

import align
import calibrate_pair as cal
import lidar_io

OWN_POST_M = 0.080          # post centres sit this far from the spin axis
OWN_POST_SLACK = 0.035
GOOD_WALL_M = 0.015         # a believable room match
GOOD_FRACTION = 0.50


def own_posts(scan):
    """The sensor's view of its own jig, inside the usual range gate."""
    local = align.polar_to_local(scan)
    r = np.hypot(local[:, 0], local[:, 1])
    near = local[(r > 0.03) & (r < OWN_POST_M + OWN_POST_SLACK)]
    if len(near) < 6:
        return []
    found = []
    for blob in cal.clusters(near, eps=0.03, min_points=4):
        d = float(np.hypot(*blob.centre))
        found.append((d, math.degrees(math.atan2(blob.centre[0],
                                                 blob.centre[1])) % 360, blob.count))
    return sorted(found)


def summarise(name, scan):
    local = align.polar_to_local(scan)
    r = np.hypot(local[:, 0], local[:, 1])
    print(f"\nsensor {name}: {len(scan)} returns, "
          f"nearest {r.min():.2f} m, furthest {r.max():.2f} m")

    posts = own_posts(scan)
    expect = OWN_POST_M - cal.JIG_POST_M / 2
    if len(posts) >= 2:
        bearings = [f"{b:.0f}deg" for _d, b, _n in posts]
        apart = abs(posts[0][1] - posts[1][1])
        apart = min(apart, 360 - apart)
        print(f"  its own jig: {len(posts)} post(s) at "
              f"{', '.join(f'{d*1000:.0f} mm' for d, _b, _n in posts)} "
              f"({', '.join(bearings)}), {apart:.0f}deg apart"
              f"   [expect 2, about {expect*1000:.0f} mm, 180deg apart]")
    else:
        print(f"  its own jig: only {len(posts)} post(s) seen near the sensor - "
              f"expected 2 at about {expect*1000:.0f} mm.")
        print("     The jig may not be seated, or the sensor is not in it.")

    pairs = cal.find_jigs(scan)
    if pairs:
        print(f"  pairs that look like the OTHER jig: {len(pairs)}")
        for s in pairs[:4]:
            print(f"     {s}")
    else:
        print("  pairs that look like the OTHER jig: none")
    return pairs


def same_room(scan_a, scan_b, step=0.4, turn=20):
    """Search for anywhere the second scan sits on top of the first."""
    A = cal.thin(align.polar_to_local(scan_a))
    B = cal.thin(align.polar_to_local(scan_b))
    tree = cKDTree(A)
    normals = align.wall_directions(A, tree)
    if normals is None:
        return None

    coarse = []
    for x in np.arange(-3.0, 3.01, step):
        for y in np.arange(-3.0, 3.01, step):
            if math.hypot(x, y) > 4.0:
                continue
            for t in range(0, 360, turn):
                d, _i = tree.query(align.transform(B, x, y, t),
                                   distance_upper_bound=0.25)
                ok = np.isfinite(d)
                if ok.sum() < 150:
                    continue
                coarse.append((float(d[ok].mean()), x, y, t))
    if not coarse:
        return None
    coarse.sort()

    best = None
    for _g, x, y, t in coarse[:12]:
        pose, _gap, _n = align.icp(B, tree, A, normals, (x, y, t))
        wall = align.wall_gap(B, tree, A, normals, pose)
        d, _i = tree.query(align.transform(B, *pose), distance_upper_bound=0.25)
        frac = float(np.isfinite(d).mean())
        if best is None or wall < best[0]:
            best = (wall, frac, pose)
    return best


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", action="append", metavar="DEV")
    p.add_argument("--rotations", type=int, default=30)
    args = p.parse_args()

    ports = args.port or lidar_io.find_ports()
    if len(ports) < 2:
        print("need two lidars plugged in; found: " + (", ".join(ports) or "none"))
        return 1

    scans = []
    for n, port in enumerate(ports[:2]):
        name = "AB"[n]
        print(f"reading {name}: {port}")
        scans.append(cal.capture(port, rotations=args.rotations, quiet=True)[0])

    pairs = [summarise("AB"[n], s) for n, s in enumerate(scans)]

    print("\n" + "=" * 68)
    print("are they in the same space?")
    best = same_room(*scans)
    if best is None:
        print("  not enough to go on - let both sensors spin a moment.")
        return 1
    wall, frac, pose = best
    gap = math.hypot(pose[0], pose[1])
    print(f"  best fit puts B {gap:.2f} m from A, at ({pose[0]:+.2f}, "
          f"{pose[1]:+.2f}) turned {pose[2]:+.1f}deg")
    print(f"  {wall*1000:.0f} mm off the walls, {frac*100:.0f}% of B's scan matched")

    if wall <= GOOD_WALL_M and frac >= GOOD_FRACTION:
        print("\n  -> they are looking at the same room.")
        if all(pairs):
            print("  -> and both can see the other's posts. Run calibrate_pair.py.")
        else:
            blind = "AB"[0] if not pairs[0] else "AB"[1]
            other = "AB"[1] if not pairs[0] else "AB"[0]
            print(f"  -> but sensor {blind} cannot find {other}'s two posts.")
            print(f"     Turn sensor {other}'s jig so its arrow points at {blind},")
            print(f"     and check nothing is standing between them.")
    else:
        print("\n  -> NO. A real match is a few mm off the walls with most of the")
        print("     scan matched; this is neither, so the two sensors are not")
        print("     seeing the same space. Something solid is between them, or")
        print("     they are in different rooms. Turning the jigs will not help.")
        print("     Put both on the open floor with a clear line of sight, then")
        print("     run this again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
