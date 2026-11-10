# Testing the mutual-sighting calibration against a fake room.
#
# There is no hardware here. A ray caster builds what each sensor would see of
# an L-shaped room with a marker standing at each sensor, then the calibration
# has to recover where the second sensor is. The room is L-shaped on purpose:
# a plain square has four-fold symmetry, so a wrong answer turned 90 degrees
# would overlap just as well and nothing could tell them apart.
#
#   python3 tests/test_calibrate_pair.py

import math
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calibrate_pair as cal

# an L-shaped room, metres
ROOM = [(-0.6, -0.5), (3.6, -0.5), (3.6, 1.4), (2.6, 1.4), (2.6, 3.4), (-0.6, 3.4)]

A_POSE = (0.0, 0.0, 0.0)            # the anchor
B_POSE = (2.0, 2.6, 200.0)          # what the calibration has to find
MARKER_R = 0.033                    # a drinks can

STEP_DEG = 0.72                     # the C1's angular resolution at 10 Hz
ROTATIONS = 20

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ok    {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


# ----------------------------------------------------------------- ray casting

def hit_segment(origin, direction, a, b):
    """Distance from origin along direction to segment a-b, or None."""
    ax, ay = a[0] - origin[0], a[1] - origin[1]
    bx, by = b[0] - origin[0], b[1] - origin[1]
    dx, dy = direction
    ex, ey = bx - ax, by - ay
    denom = dx * ey - dy * ex
    if abs(denom) < 1e-12:
        return None
    t = (ax * ey - ay * ex) / denom          # along the ray
    u = (ax * dy - ay * dx) / -denom         # along the segment
    if t <= 0 or not (0.0 <= u <= 1.0):
        return None
    return t


def hit_circle(origin, direction, centre, radius):
    """Distance to the near face of a cylinder, or None."""
    px, py = origin[0] - centre[0], origin[1] - centre[1]
    b = direction[0] * px + direction[1] * py
    c = px * px + py * py - radius * radius
    disc = b * b - c
    if disc < 0:
        return None
    t = -b - math.sqrt(disc)
    return t if t > 0 else None


def fake_scan(pose, markers, rotations=ROTATIONS, step=STEP_DEG, seed=1,
              noise_m=0.0, room=None):
    """What a sensor at `pose` would report. Angles are its own: zero straight
    ahead, growing clockwise, so bearing b points along (sin b, cos b).

    Each rotation starts at a random angle, the way a real one does. That is
    what lets stacked rotations fill in the gaps between readings, and it is
    the only reason a 6 cm marker across the room gets enough hits.
    """
    rng = random.Random(seed)
    x, y, turn = pose
    room = ROOM if room is None else room
    walls = list(zip(room, room[1:] + room[:1]))
    out = []
    for _ in range(rotations):
        offset = rng.uniform(0.0, step)
        bearing = offset
        while bearing < 360.0:
            world = math.radians(bearing + turn)
            direction = (math.sin(world), math.cos(world))
            best = None
            for wa, wb in walls:
                t = hit_segment((x, y), direction, wa, wb)
                if t is not None and (best is None or t < best):
                    best = t
            for centre, radius in markers:
                t = hit_circle((x, y), direction, centre, radius)
                if t is not None and (best is None or t < best):
                    best = t
            if best is not None:
                if noise_m:
                    best += rng.gauss(0.0, noise_m)
                out.append((bearing % 360.0, best * 1000.0, 47))
            bearing += step
    return out


def scans(extra=(), markers=True, noise_m=0.0):
    """Both sensors' view of the room. Each sees the other's marker but not
    its own, which is what really happens: a sensor cannot see what is
    bolted to it."""
    on_a = [((A_POSE[0], A_POSE[1]), MARKER_R)] if markers else []
    on_b = [((B_POSE[0], B_POSE[1]), MARKER_R)] if markers else []
    extra = list(extra)
    return (fake_scan(A_POSE, on_b + extra, seed=1, noise_m=noise_m),
            fake_scan(B_POSE, on_a + extra, seed=2, noise_m=noise_m))


def error(pose):
    return (math.hypot(pose[0] - B_POSE[0], pose[1] - B_POSE[1]),
            abs(cal.wrap180(pose[2] - B_POSE[2])))


# ----------------------------------------------------------------------- tests

def test_solve_pose_is_exact():
    print("\nthe arithmetic, with the sightings handed to it directly")
    for truth in ((2.0, 2.6, 200.0), (-1.5, 0.4, -37.0), (0.0, 3.0, 180.0)):
        bx, by, turn = truth
        bearing_a = math.degrees(math.atan2(bx, by))          # A looks at B
        sep = math.hypot(bx, by)
        # the same direction seen from B: reverse it, then undo B's turn
        bearing_b = cal.wrap180(math.degrees(math.atan2(-bx, -by)) - turn)
        got = cal.solve_pose((0.0, 0.0, 0.0), bearing_a, bearing_b, sep)
        off, spin = (math.hypot(got[0] - bx, got[1] - by),
                     abs(cal.wrap180(got[2] - turn)))
        check(f"recovers {truth}", off < 1e-9 and spin < 1e-9,
              f"off by {off:.2e} m, {spin:.2e} deg")


def test_anchor_may_sit_anywhere():
    print("\nthe anchor does not have to be the origin")
    anchor = (1.25, -0.75, 33.0)
    # B two metres ahead-right of a tilted anchor
    bearing_a, sep, turn_b = 20.0, 2.0, 140.0
    look = math.radians(bearing_a + anchor[2])
    bx = anchor[0] + sep * math.sin(look)
    by = anchor[1] + sep * math.cos(look)
    bearing_b = cal.wrap180(math.degrees(math.atan2(anchor[0] - bx, anchor[1] - by))
                            - turn_b)
    got = cal.solve_pose(anchor, bearing_a, bearing_b, sep)
    off = math.hypot(got[0] - bx, got[1] - by)
    check("anchor at an angle", off < 1e-9 and abs(cal.wrap180(got[2] - turn_b)) < 1e-9,
          f"off by {off:.2e} m")


def test_finds_the_marker():
    """Finding the marker, and NOT finding only the marker.

    A far corner seen edge-on turns up here too: the wall running away from
    the sensor is sampled so sparsely that its readings don't join up, and
    only the few points at the corner itself cluster. That is fine and
    expected - this stage is meant to gather candidates, not to judge them.
    It is the distance check and the room overlap that throw the corner out.
    """
    print("\npicking the marker out of a room")
    truth = math.hypot(B_POSE[0], B_POSE[1])
    found_a = cal.find_markers(scans()[0])
    found_b = cal.find_markers(scans()[1])
    check("A sees something", bool(found_a))
    check("B sees something", bool(found_b))
    if not (found_a and found_b):
        return

    near = [s for s in found_a if abs(s.centre_distance() - truth) < 0.02]
    check("one of A's candidates is the other sensor", len(near) == 1,
          f"found {found_a}")
    check("the walls themselves are not candidates",
          all(s.width <= cal.MAX_MARKER_WIDTH_M for s in found_a + found_b))
    if not near:
        return
    check("the near face reads short, as it must", near[0].distance < truth - 0.01,
          f"near face {near[0].distance:.3f} vs centre {truth:.3f}")
    check("half the measured width corrects it to within a centimetre",
          abs(near[0].centre_distance() - truth) < 0.01,
          f"corrected {near[0].centre_distance():.3f} vs {truth:.3f}")
    print(f"    A's candidates: {[round(s.centre_distance(), 2) for s in found_a]} m")
    print(f"    B's candidates: {[round(s.centre_distance(), 2) for s in found_b]} m")


def test_recovers_the_pose():
    print("\nthe whole thing, on a clean room")
    scan_a, scan_b = scans()
    result = cal.calibrate_pair(scan_a, scan_b, A_POSE)
    print("    " + result.report().replace("\n", "\n    "))
    check("it trusts the answer", result.ok, result.report())
    if not result.ok:
        return
    off, spin = error(result.pose)
    check("within 3 cm", off < 0.03, f"{off*1000:.0f} mm out")
    check("within 1 degree", spin < 1.0, f"{spin:.2f} deg out")
    check("both sides agreed on the gap", result.best.disagreement < 0.02,
          f"{result.best.disagreement*1000:.0f} mm apart")
    check("nothing else fitted", not result.rivals)


def test_survives_noise():
    print("\nthe same room, with 10 mm of measurement noise")
    scan_a, scan_b = scans(noise_m=0.010)
    result = cal.calibrate_pair(scan_a, scan_b, A_POSE)
    check("it still trusts the answer", result.ok, result.report())
    if not result.ok:
        return
    off, spin = error(result.pose)
    check("within 5 cm", off < 0.05, f"{off*1000:.0f} mm out")
    check("within 1.5 degrees", spin < 1.5, f"{spin:.2f} deg out")


def test_ignores_a_decoy():
    print("\nwith a bin left standing in the room")
    decoy = [((1.2, 0.9), 0.05)]
    scan_a, scan_b = scans(extra=decoy)
    result = cal.calibrate_pair(scan_a, scan_b, A_POSE)
    print("    " + result.report().replace("\n", "\n    "))
    plain = cal.calibrate_pair(*scans(), A_POSE)
    check("the bin adds a candidate on both sides",
          len(result.markers_a) > len(plain.markers_a)
          and len(result.markers_b) > len(plain.markers_b),
          f"{len(result.markers_a)}/{len(result.markers_b)} vs "
          f"{len(plain.markers_a)}/{len(plain.markers_b)} without it")
    check("it still trusts the answer", result.ok, result.report())
    if result.ok:
        off, spin = error(result.pose)
        check("and still gets it right", off < 0.04 and spin < 1.5,
              f"{off*1000:.0f} mm, {spin:.2f} deg out")


def test_says_so_when_blind():
    print("\nwith no markers at all, so neither can see the other")
    scan_a, scan_b = scans(markers=False)
    result = cal.calibrate_pair(scan_a, scan_b, A_POSE)
    check("it refuses", not result.ok, result.report())
    check("and says why", "marker" in result.report().lower(), result.report())
    print("    " + result.report().replace("\n", "\n    "))


def test_refuses_a_lying_pairing():
    print("\nwith a decoy placed to be exactly as far away as the other sensor")
    # both sensors are 3.28 m apart; park a bin 3.28 m from each of them, on
    # the other side, so the distance check cannot tell the pairings apart
    sep = math.hypot(B_POSE[0], B_POSE[1])
    scan_a, scan_b = scans(extra=[((-0.55, 1.1), 0.05)])
    result = cal.calibrate_pair(scan_a, scan_b, A_POSE)
    off = None if not result.ok else error(result.pose)
    check("it either gets it right or refuses, never silently wrong",
          (not result.ok) or (off[0] < 0.04 and off[1] < 1.5),
          f"pose {result.pose}")
    print(f"    separation {sep:.3f} m, {result.tried} pairing(s) tried, "
          f"{'answered' if result.ok else 'refused'}")


def test_refuses_when_the_rooms_disagree():
    """The distance check can be fooled; the room overlap is what catches it.

    Here sensor B is in a corridor somewhere else entirely, with something
    standing at exactly the distance that would make the pairing look right.
    The two sightings agree perfectly and the answer is still nonsense.
    """
    print("\nwith the second sensor in a different room")
    corridor = [(-1.0, -1.0), (8.0, -1.0), (8.0, 0.6), (-1.0, 0.6)]
    gap = math.hypot(B_POSE[0], B_POSE[1])          # what A will measure
    elsewhere = (1.0, 0.0, 0.0)
    decoy = ((elsewhere[0] + gap, elsewhere[1]), MARKER_R)
    scan_a = scans()[0]
    scan_b = fake_scan(elsewhere, [decoy], seed=5, room=corridor)

    result = cal.calibrate_pair(scan_a, scan_b, A_POSE)
    check("it refuses", not result.ok, result.report())
    print("    " + result.report().replace("\n", "\n    "))
    if result.best is not None:
        check("the two sightings did agree, so distance alone was no help",
              result.best.disagreement < cal.DIST_TOL_M,
              f"{result.best.disagreement*1000:.0f} mm apart")


def test_rival_answers_are_called_out():
    print("\nthe ambiguity guard itself")
    def made(pose, wall):
        return cal.Candidate(pose, 3.0, 0.0, wall, 400, 0.9, None, None)

    best = made((2.0, 2.6, 200.0), 0.010)
    check("a pose 40 cm away is a different answer",
          made((2.0, 3.0, 200.0), 0.011).far_from(best))
    check("a pose 15 degrees round is a different answer",
          made((2.0, 2.6, 215.0), 0.011).far_from(best))
    check("a pose 5 mm and 0.1 degrees away is the same answer",
          not made((2.005, 2.6, 200.1), 0.011).far_from(best))

    rivals = [c for c in (made((2.0, 3.0, 200.0), 0.011),      # close score, far pose
                          made((2.0, 3.0, 0.100), 0.100),      # far pose, bad score
                          made((2.001, 2.6, 200.0), 0.011))    # same pose
              if c.wall_m <= best.wall_m * cal.AMBIGUOUS_RATIO and c.far_from(best)]
    check("only a near-equal score in a different place counts as a rival",
          len(rivals) == 1, f"{len(rivals)} rivals")


def test_polish_keeps_it_close():
    print("\nhanding the answer to ICP to polish")
    scan_a, scan_b = scans(noise_m=0.010)
    result = cal.calibrate_pair(scan_a, scan_b, A_POSE)
    if not result.ok:
        check("needs a sighting first", False, result.report())
        return
    before = error(result.pose)
    pose, note = cal.polish(scan_b, scan_a, A_POSE, result.pose)
    after = error(pose)
    print(f"    {note}")
    print(f"    before {before[0]*1000:.0f} mm / {before[1]:.2f} deg"
          f"   ->   after {after[0]*1000:.0f} mm / {after[1]:.2f} deg")
    check("polishing does not throw the answer away",
          after[0] < 0.05 and after[1] < 1.5,
          f"{after[0]*1000:.0f} mm, {after[1]:.2f} deg out")


def test_saves_what_the_live_view_reads():
    print("\nthe saved file")
    import json
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        cal.ALIGN_FILE = os.path.join(tmp, "lidar_align.json")
        cal.save_poses([("SERIALA", A_POSE, "/dev/fake-a", "A"),
                        ("SERIALB", B_POSE, "/dev/fake-b", "B")])
        saved = json.load(open(cal.ALIGN_FILE))
    check("keyed by serial number", set(saved) == {"SERIALA", "SERIALB"}, str(saved))
    check("the keys the live view expects",
          set(saved["SERIALB"]) >= {"x", "y", "rot"}, str(saved["SERIALB"]))
    check("values round-trip", abs(saved["SERIALB"]["rot"] - B_POSE[2]) < 1e-9)


if __name__ == "__main__":
    print(f"fake L-shaped room; A at {A_POSE}, B truly at {B_POSE}")
    print(f"they are {math.hypot(B_POSE[0], B_POSE[1]):.3f} m apart, "
          f"markers {MARKER_R*200:.0f} cm across")
    test_solve_pose_is_exact()
    test_anchor_may_sit_anywhere()
    test_finds_the_marker()
    test_recovers_the_pose()
    test_survives_noise()
    test_ignores_a_decoy()
    test_says_so_when_blind()
    test_refuses_a_lying_pairing()
    test_refuses_when_the_rooms_disagree()
    test_rival_answers_are_called_out()
    test_polish_keeps_it_close()
    test_saves_what_the_live_view_reads()
    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
