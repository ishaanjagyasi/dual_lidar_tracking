# Calibrating two lidars by letting them see each other.
#
#   python3 calibrate_pair.py
#
# The sensors are physical objects sitting in each other's view. If both are at
# the same height, A sees B and B sees A. That one mutual sighting is enough to
# work out everything:
#
#   where B is      A measured the direction and the distance to it
#   which way B     B measured the direction back to A, and we already know
#   is facing       which direction that *should* be, so the difference is
#                   how far B is turned
#
# Three unknowns, three measurements, solved outright. No searching, no
# starting guess, nothing to get stuck in.
#
# That matters because the other method - ICP in align.py, the K key in the
# live view - slides one sensor's points around until they sit on top of the
# other's. It only ever looks at the *nearest* points, so from a poor starting
# guess it can settle onto the wrong wall and be confidently wrong, and in a
# plain room (a corridor, a bare square) several answers look equally good.
# This script never guesses, so it cannot do that.
#
# What it cannot do is beat ICP on the last couple of centimetres. A lidar
# measures the near *surface* of a marker, not its middle, and a marker taped
# beside a sensor is not exactly on that sensor's spin axis. Both are
# centimetre-scale errors. So by default this hands its answer to ICP to
# polish: the sighting gets ICP into the right basin, ICP squeezes out the last
# of the error against the walls. Use --no-polish to see the raw sighting.
#
#
# BEFORE YOU RUN IT
#
# Each sensor needs something the other can measure, and it has to sit on that
# sensor's spin axis, because that is the point being located. Two things make
# that awkward, both out of SLAMTEC's own datasheet:
#
#   the laser sits at 29.8 mm, 11.5 mm BELOW the top of the 41.3 mm case, so a
#   marker resting on top of a sensor is above the beam and invisible; and
#
#   the scan plane is only promised to be level to within 1.5 degrees, which
#   over 3.4 m of carpet is 89 mm of drift up or down, so a short marker at
#   exactly 29.8 mm may be missed completely.
#
# Hence hardware/calibration_target.scad: a jig that drops around the sensor
# and stands two 25 mm posts 120 mm tall, one each side of the spin axis,
# 160 mm apart. Nothing can sit on the axis - that is where the sensor is - but
# the midpoint of two posts straddling it is the axis exactly, whichever way
# round the jig is turned. Print one per sensor, aim the arrows at each other,
# run this, take them off again.
#
# Without a jig it will fall back to single clumps, so a drinks can or a bottle
# standing against each sensor still works; it is just less accurate, because
# one lone marker cannot sit on the axis and is off by however far it misses.
#
# Either way, stand clear. The room must be still - a person standing in it is
# another marker-shaped thing for this to consider.
#
#
# HOW IT TELLS A MARKER FROM THE FURNITURE
#
# It doesn't, on its own, and it does not simply trust the jig either: a room
# can easily throw up two odds and ends 160 mm apart. So the jig is tried
# first, single clumps second, and whatever is proposed has to survive the
# same two checks:
#
#   both sides must agree on the gap   A and B measure the same distance
#                                      between the two of them. Two readings of
#                                      one number, so they must match - a free
#                                      check that costs nothing.
#   the room must line up              a pairing gives a position for B; with
#                                      the right pairing B's whole scan lands
#                                      on top of A's walls, and with a wrong
#                                      one it lands nowhere near.
#
# If two different pairings both pass, it says so and refuses to save rather
# than pick one. Usually that means something marker-shaped is in the room.

import argparse
import json
import math
import os
import time
from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

import align
import lidar_io
import tracker as person

HERE = os.path.dirname(os.path.abspath(__file__))
ALIGN_FILE = os.path.join(HERE, "lidar_align.json")   # same file the live view uses

# the printed jig in hardware/calibration_target.scad
JIG_SPAN_M = 0.160            # between the two posts' centres (2 x 80 mm)
JIG_SPAN_TOL_M = 0.030        # how far the measured span may be out
JIG_POST_M = 0.025            # post diameter
JIG_POST_TOL_M = 0.030        # the two posts must measure alike
JIG_POST_MAX_M = 0.100        # and neither may be furniture-sized

# picking markers out of a scan
MIN_SEP_M = 0.30              # closer than this and it isn't the other sensor
MAX_SEP_M = 12.0              # the C1's range
MARKER_EPS_M = 0.03           # points this close together are the same object.
                              # Small, because the jig's posts stand only 40 mm
                              # clear of the sensor's own case and a wider
                              # reach would swallow all three into one clump.
MIN_MARKER_POINTS = 4
MAX_MARKER_WIDTH_M = 0.30     # wider than this is furniture or a wall
RING_CLEAR_M = 0.08           # a lone marker has empty space around it. The
                              # jig's posts do not - the sensor's own case is
                              # only about 45 mm away - so this is applied when
                              # looking for single clumps and skipped when
                              # looking for the jig, whose two-post geometry
                              # is a far better filter anyway.
MAX_BLOBS = 150               # how many clumps to consider at all
MAX_CANDIDATES = 40           # don't try every pairing in a cluttered room

# judging a pairing
DIST_TOL_M = 0.15             # how far the two measured gaps may disagree
MAX_WALL_M = align.GOOD_GAP_M # B's points must land this close to A's walls
MIN_MATCHED_FRACTION = 0.30   # and this much of B's scan must land on them
AMBIGUOUS_RATIO = 1.30        # a rival scoring within this is "just as good"
AMBIGUOUS_MOVE_M = 0.10       # ...and is a real rival if it sits this far off
AMBIGUOUS_TURN_DEG = 2.0

# capturing
WARMUP_ROTATIONS = 20         # the first second or two is spin-up; throw it away
CAPTURE_ROTATIONS = 20        # stacking rotations fills in the gaps between
                              # readings, so a small marker gets enough hits
MAX_POINTS = 4000             # thin bigger clouds; the fit doesn't need them


# --------------------------------------------------------------------- geometry
# Angles are the sensor's own: degrees, zero straight ahead, growing clockwise.
# A reading sits at (d*sin, d*cos), so "ahead" is +y and "right" is +x. This
# matches align.transform and Sensor.to_world in the live view.

def wrap180(deg):
    return (deg + 180.0) % 360.0 - 180.0


def bearing_of(vec):
    """Which way a point lies, in the same degrees the sensor reports."""
    return math.degrees(math.atan2(vec[0], vec[1]))


def solve_pose(anchor, bearing_a, bearing_b, separation):
    """Where the second sensor is, from the two sightings.

    anchor      (x, y, turn_deg) of the sensor we are measuring from
    bearing_a   the direction A saw B in, in A's own degrees
    bearing_b   the direction B saw A in, in B's own degrees
    separation  how far apart they are, in metres

    Position: walk `separation` from A in the direction A was looking.
    Turn: A looking at B and B looking at A are opposite directions, so B's
    view of A must point along (bearing_a + anchor_turn + 180) once B's own
    turn is added in. Whatever closes that gap is B's turn.
    """
    xa, ya, ra = anchor
    look = math.radians(bearing_a + ra)
    return (xa + separation * math.sin(look),
            ya + separation * math.cos(look),
            wrap180(bearing_a + ra + 180.0 - bearing_b))


def thin(points):
    if len(points) <= MAX_POINTS:
        return points
    return points[:: int(np.ceil(len(points) / MAX_POINTS))]


# ---------------------------------------------------------------------- markers

@dataclass
class Sighting:
    """Something one sensor can see that might be the other sensor.

    Either a single clump - a drinks can, say - or, better, the printed jig's
    two posts, in which case bearing and distance are of the point midway
    between them, which is the other sensor's spin axis exactly.
    """
    bearing: float      # degrees, the sensor's own
    distance: float     # metres to its near face
    width: float        # metres across, as measured
    points: int
    kind: str = "clump"     # "jig" once the two posts have been recognised
    span: float = None      # the measured gap between those posts

    def centre_distance(self, radius=None):
        """Distance to the middle of it. The laser stops at the near surface,
        so the middle is half a width further out. For the jig that correction
        is the same: both posts are measured on their near faces, so the point
        midway between them is short by half a post as well."""
        return self.distance + (self.width / 2.0 if radius is None else radius)

    def __str__(self):
        what = (f"jig, posts {self.span*1000:.0f} mm apart" if self.kind == "jig"
                else f"{self.width*100:.0f} cm across")
        return (f"{self.bearing:7.2f}deg  {self.distance:6.3f} m  "
                f"({what}, {self.points} points)")


def clusters(points, eps=MARKER_EPS_M, min_points=MIN_MARKER_POINTS):
    """Group points that touch. Deliberately not tracker.find_blobs: that one
    throws away anything under 2 cm as noise, and a marker across the room is
    a handful of points sitting almost on top of each other."""
    if len(points) < min_points:
        return []
    tree = cKDTree(points)
    seen = np.zeros(len(points), dtype=bool)
    out = []
    for start in range(len(points)):
        if seen[start]:
            continue
        group, queue = [], [start]
        seen[start] = True
        while queue:
            i = queue.pop()
            group.append(i)
            for j in tree.query_ball_point(points[i], eps):
                if not seen[j]:
                    seen[j] = True
                    queue.append(j)
        if len(group) >= min_points:
            out.append(person.Blob(points[group]))
    return out


def candidate_blobs(scan, min_sep=None, max_sep=None, clear=RING_CLEAR_M):
    """Every small clump in one sensor's scan, nearest first.

    `clear` is how much empty space a clump must have around it. Zero turns
    that test off, which is what the jig needs: its posts stand close to the
    sensor's own case and would be thrown out.
    """
    min_sep = MIN_SEP_M if min_sep is None else min_sep
    max_sep = MAX_SEP_M if max_sep is None else max_sep
    local = align.polar_to_local(scan)
    if len(local) < MIN_MARKER_POINTS:
        return []

    radius = np.hypot(local[:, 0], local[:, 1])
    in_range = local[(radius >= min_sep) & (radius <= max_sep)]
    if len(in_range) < MIN_MARKER_POINTS:
        return []

    # the ring test below asks what else is nearby, so it has to see the whole
    # scan, not just the part inside the range gate
    tree = cKDTree(local)

    found = []
    for blob in clusters(in_range):
        if blob.size > MAX_MARKER_WIDTH_M:
            continue
        # every point of the blob is within size/2 of its middle, so anything
        # else inside this ball is a neighbour that shouldn't be there
        if clear > 0:
            reach = blob.size / 2.0 + clear
            nearby = int(tree.query_ball_point(blob.centre, reach,
                                               return_length=True))
            if nearby > blob.count:
                continue
        found.append(blob)
    found.sort(key=lambda b: float(np.hypot(*b.centre)))
    return found[:MAX_BLOBS]


def _sighting(centre, width, points, kind="clump", span=None):
    return Sighting(bearing_of(centre), float(np.hypot(*centre)),
                    float(width), int(points), kind, span)


def find_markers(scan, min_sep=None, max_sep=None):
    """Each clump on its own - a drinks can, or a single post. Nearest first."""
    return [_sighting(b.centre, b.size, b.count)
            for b in candidate_blobs(scan, min_sep, max_sep)][:MAX_CANDIDATES]


def find_jigs(scan, span=JIG_SPAN_M, tol=JIG_SPAN_TOL_M,
              min_sep=None, max_sep=None):
    """The printed jig: two posts a known distance apart, straddling the
    sensor's spin axis.

    Nothing can sit on the axis itself - that is where the sensor is - so the
    jig puts a post either side of it, exactly opposite. The midpoint of the
    two is the axis, whichever way the jig is turned, and the distance between
    them is fixed by the print, so it is a signature almost nothing else in a
    room has. The sensor's own case sits between the posts and may well show up
    as a third clump; it is simply ignored.

    Returns a Sighting per pair, at the midpoint, nearest first.
    """
    blobs = candidate_blobs(scan, min_sep, max_sep, clear=0.0)
    found = []
    for i in range(len(blobs)):
        for j in range(i + 1, len(blobs)):
            a, b = blobs[i], blobs[j]
            gap = float(np.hypot(*(a.centre - b.centre)))
            if abs(gap - span) > tol:
                continue
            # The posts are two identical prints at nearly the same range, so
            # they should measure nearly the same. Two unrelated bits of room
            # furniture that happen to be the right distance apart usually
            # don't, and this is the cheapest way to say so.
            if abs(a.size - b.size) > JIG_POST_TOL_M:
                continue
            if max(a.size, b.size) > JIG_POST_MAX_M:
                continue
            found.append(_sighting((a.centre + b.centre) / 2.0,
                                   (a.size + b.size) / 2.0,
                                   a.count + b.count, "jig", gap))
    found.sort(key=lambda s: s.distance)
    return found[:MAX_CANDIDATES]


# ---------------------------------------------------------------------- scoring

def world_cloud(scan, pose):
    """One sensor's readings, placed on the shared map."""
    return align.transform(thin(align.polar_to_local(scan)), *pose)


def overlap(local, tree, target, normals, pose):
    """How well a pose makes one scan sit on the other's walls.

    Returns (mean distance off the walls in metres, points matched, fraction
    matched), or None if almost nothing matched. Measuring to the wall rather
    than to the nearest point matters: the two sensors never sample the same
    spots, so point-to-point distance is mostly just the gap between readings.
    """
    moved = align.transform(local, *pose)
    dist, idx = tree.query(moved, distance_upper_bound=align.MAX_PAIR_M)
    ok = np.isfinite(dist)
    matched = int(ok.sum())
    if matched < align.MIN_PAIRS:
        return None
    off = np.einsum("ij,ij->i", normals[idx[ok]], moved[ok] - target[idx[ok]])
    return float(np.abs(off).mean()), matched, matched / len(moved)


@dataclass
class Candidate:
    pose: tuple
    separation: float
    disagreement: float
    wall_m: float
    matched: int
    fraction: float
    seen_by_a: Sighting
    seen_by_b: Sighting

    def far_from(self, other):
        return (math.hypot(self.pose[0] - other.pose[0], self.pose[1] - other.pose[1])
                > AMBIGUOUS_MOVE_M
                or abs(wrap180(self.pose[2] - other.pose[2])) > AMBIGUOUS_TURN_DEG)


@dataclass
class Result:
    pose: tuple = None          # None means: don't trust this
    lines: tuple = ()
    best: Candidate = None
    rivals: tuple = ()
    markers_a: tuple = ()
    markers_b: tuple = ()
    tried: int = 0

    @property
    def ok(self):
        return self.pose is not None

    def report(self):
        return "\n".join(self.lines)


def _with_hint(result, jigs_a, jigs_b):
    """One sensor showing the jig's pair and the other not is worth saying out
    loud: it means the jig the blind one is looking at is a quarter turn out,
    so its two posts line up one behind the other and only the near one comes
    back.

    Note which sensor that is. A sees B's jig, so an empty jigs_a means B's jig
    is the one at fault - the sensor that CAN see a pair is the one whose own
    jig needs turning, because the other one is looking straight at it.
    """
    if bool(jigs_a) == bool(jigs_b):
        return result
    at_fault = "A" if jigs_a else "B"       # this one's own jig is edge-on
    blind = "B" if jigs_a else "A"
    return Result(result.pose, result.lines + (
        f"  Sensor {at_fault} can see a pair of posts; sensor {blind} cannot.",
        f"  So it is sensor {at_fault}'s OWN jig that is turned a quarter turn out:",
        f"  {blind} is looking straight at it and sees one post hiding behind the",
        f"  other. Turn sensor {at_fault}, or just its jig, so the arrow points at "
        f"sensor {blind}.",
    ), result.best, result.rivals, result.markers_a, result.markers_b, result.tried)


def _solve(markers_a, markers_b, anchor, marker_radius, how,
           target, tree, normals, local_b):
    """Try every pairing of what A can see against what B can see, and keep
    the one that survives both checks. Returns a Result."""
    candidates, tried = [], 0
    for sa in markers_a:
        for sb in markers_b:
            da = sa.centre_distance(marker_radius)
            db = sb.centre_distance(marker_radius)
            disagreement = abs(da - db)
            tried += 1
            if disagreement > DIST_TOL_M:
                continue        # they are not looking at each other
            separation = (da + db) / 2.0
            pose = solve_pose(anchor, sa.bearing, sb.bearing, separation)
            scored = overlap(local_b, tree, target, normals, pose)
            if scored is None:
                continue
            wall, matched, fraction = scored
            candidates.append(Candidate(pose, separation, disagreement,
                                        wall, matched, fraction, sa, sb))

    head = (f"matching on {how}: {len(markers_a)} for A, {len(markers_b)} for B, "
            f"{tried} pairing(s) tried")

    if not candidates:
        return Result(
            markers_a=markers_a, markers_b=markers_b, tried=tried,
            lines=(head,
                   "none of them worked: no two agreed on the distance between",
                   "them, or the agreeing ones put the rooms nowhere near each other.",
                   "Check that both markers are at the height the other sensor",
                   "scans at, and that nothing is standing between them."))

    candidates.sort(key=lambda c: c.wall_m)
    strong = [c for c in candidates if c.fraction >= MIN_MATCHED_FRACTION]
    best = (strong or candidates)[0]
    rivals = tuple(c for c in (strong or candidates)[1:]
                   if c.wall_m <= best.wall_m * AMBIGUOUS_RATIO and c.far_from(best))

    lines = [
        head,
        f"  A saw B at  {best.seen_by_a}",
        f"  B saw A at  {best.seen_by_b}",
        f"  the two measured the gap between them as "
        f"{best.seen_by_a.centre_distance(marker_radius):.3f} m and "
        f"{best.seen_by_b.centre_distance(marker_radius):.3f} m "
        f"- {best.disagreement*1000:.0f} mm apart",
        f"  so B is at ({best.pose[0]:+.3f}, {best.pose[1]:+.3f}) m, "
        f"turned {best.pose[2]:+.2f}deg",
        f"  the rooms then line up to {best.wall_m*1000:.0f} mm off the walls, "
        f"{best.matched} points matched ({best.fraction*100:.0f}%)",
    ]

    if rivals:
        lines.append(f"  AMBIGUOUS: {len(rivals)} other pairing(s) fit just as well, "
                     "one of them")
        lines.append(f"  putting B at ({rivals[0].pose[0]:+.3f}, "
                     f"{rivals[0].pose[1]:+.3f}) m turned {rivals[0].pose[2]:+.2f}deg.")
        lines.append("  Something else in the room looks like a marker. Clear it "
                     "and run again.")
        return Result(None, tuple(lines), best, rivals, markers_a, markers_b, tried)

    if best.wall_m > MAX_WALL_M:
        lines.append(f"  {best.wall_m*1000:.0f} mm off the walls is too far out to "
                     "believe. The two sightings")
        lines.append("  agreed, so they were looking at each other - but the rooms "
                     "they see don't")
        lines.append("  match, so they are not in the same room, or something moved "
                     "between the")
        lines.append("  two captures.")
        return Result(None, tuple(lines), best, rivals, markers_a, markers_b, tried)

    if not strong:
        lines.append(f"  only {best.fraction*100:.0f}% of B's scan landed on A's - "
                     "too little to believe.")
        lines.append("  One of them is probably seeing a lot of room the other "
                     "cannot.")
        return Result(None, tuple(lines), best, rivals, markers_a, markers_b, tried)

    return Result(best.pose, tuple(lines), best, rivals, markers_a, markers_b, tried)


def calibrate_pair(scan_a, scan_b, anchor=(0.0, 0.0, 0.0), marker_radius=None,
                   min_sep=None, max_sep=None, span=JIG_SPAN_M):
    """Work out where sensor B is, given both sensors' scans.

    scan_a, scan_b  [(angle_deg, dist_mm, quality)] from each sensor
    anchor          (x, y, turn_deg) of sensor A on the shared map
    marker_radius   metres, if you know how fat the markers are; by default
                    half the width each sensor actually measured is used
    min_sep,        how far apart the sensors could possibly be, in metres
    max_sep
    span            the printed jig's post spacing. None skips looking for it
                    and matches single clumps instead - a drinks can, say.

    The jig is tried first and single clumps are the fallback, but the jig is
    not simply believed: a room can easily throw up two odds and ends the right
    distance apart, so a jig answer still has to pass the same two checks as
    any other, and if it doesn't the clumps get their turn.

    Returns a Result. result.pose is None when the answer can't be trusted,
    and result.lines always says why.
    """
    target = world_cloud(scan_a, anchor)
    tree = cKDTree(target)
    normals = align.wall_directions(target, tree)
    local_b = thin(align.polar_to_local(scan_b))
    if normals is None or len(local_b) < align.MIN_PAIRS:
        return Result(lines=("not enough points yet - let both sensors spin a moment",))

    tries = []
    jigs_a = jigs_b = ()
    if span:
        jigs_a = tuple(find_jigs(scan_a, span, JIG_SPAN_TOL_M, min_sep, max_sep))
        jigs_b = tuple(find_jigs(scan_b, span, JIG_SPAN_TOL_M, min_sep, max_sep))
        tries.append(("the jig's two posts", jigs_a, jigs_b))
    tries.append(("single clumps",
                  tuple(find_markers(scan_a, min_sep, max_sep)),
                  tuple(find_markers(scan_b, min_sep, max_sep))))

    first_failure = None
    for how, markers_a, markers_b in tries:
        if not markers_a or not markers_b:
            continue
        result = _solve(markers_a, markers_b, anchor, marker_radius, how,
                        target, tree, normals, local_b)
        if result.ok:
            return result
        if first_failure is None:
            first_failure = result
    if first_failure is not None:
        return _with_hint(first_failure, jigs_a, jigs_b)

    markers_a = tries[-1][1]
    markers_b = tries[-1][2]
    blind = [n for n, found in (("A", markers_a), ("B", markers_b)) if not found]
    who = ("neither sensor" if len(blind) == 2 else f"sensor {blind[0]}")
    return Result(
        markers_a=markers_a, markers_b=markers_b,
        lines=(
            f"{who} could not see anything marker-shaped.",
            "Each sensor needs the printed jig around it (see hardware/), or",
            "failing that something upright 5-10 cm across standing against it,",
            "tall enough to cross the height the other sensor scans at.",
            "A bare C1 is a 55 mm box and the other one's beam goes over it.",
        ))


def polish(scan_b, scan_a, anchor, pose):
    """Hand the sighting's answer to ICP to squeeze out the last few mm.

    Returns (pose, note). The sighting's own pose is kept if ICP declines.
    """
    refined, note = align.calibrate(scan_b, world_cloud(scan_a, anchor), pose)
    if refined is None:
        return pose, f"ICP would not improve on it ({note}) - keeping the sighting"
    moved = math.hypot(refined[0] - pose[0], refined[1] - pose[1])
    turned = abs(wrap180(refined[2] - pose[2]))
    return refined, (f"ICP nudged it {moved*1000:.0f} mm and {turned:.2f}deg "
                     f"against the walls - {note}")


# ---------------------------------------------------------------- the sensors

def capture(port, baud=lidar_io.BAUD, rotations=CAPTURE_ROTATIONS,
            warmup=WARMUP_ROTATIONS, quiet=False):
    """Stack a couple of seconds of rotations from one sensor.

    One sensor at a time is fine: everything being measured is standing still,
    so the two scans don't have to be taken at the same moment. It also keeps
    this off the live view's threading entirely.

    Stacking matters. A single rotation puts readings 0.8 deg apart, which at
    3 m is one hit every 4 cm - a drinks can gets two. The sensor doesn't land
    on the same angles each time round, so twenty rotations give twenty times
    the detail on the marker.
    """
    if not quiet:
        print(f"  opening {port} ...")
    lidar, info, health = lidar_io.open_lidar(port, baud, quiet=quiet)
    serial = (info or {}).get("serialnumber")
    points = []
    try:
        for n, scan in enumerate(lidar_io.rotations(lidar), 1):
            if n > warmup:
                points.extend(scan)
            if n >= warmup + rotations:
                break
    finally:
        lidar_io.close_lidar(lidar)
    if not quiet:
        print(f"  {len(points)} points over {rotations} rotations, "
              f"serial {serial}, health {health[0] if health else '?'}")
    return points, serial


def load_poses():
    if not os.path.exists(ALIGN_FILE):
        return {}
    try:
        return json.load(open(ALIGN_FILE))
    except Exception as exc:
        print(f"  (could not read {os.path.basename(ALIGN_FILE)}: {exc})")
        return {}


def save_poses(entries):
    """Write the same file, in the same shape, the live view reads."""
    saved = load_poses()
    for serial, pose, port, name in entries:
        if not serial:
            print("  that sensor never reported a serial number - not saving it")
            continue
        saved[serial] = {"x": pose[0], "y": pose[1], "rot": pose[2],
                         "port_last_seen": port, "name": name}
    with open(ALIGN_FILE, "w") as fh:
        json.dump(saved, fh, indent=2)
    return f"written to {os.path.basename(ALIGN_FILE)}"


def main():
    p = argparse.ArgumentParser(
        description="Calibrate two lidars by letting them see each other.")
    p.add_argument("--port", action="append", metavar="DEV",
                   help="a serial port; give it twice. The first is the anchor "
                        "and keeps its place. Found automatically if omitted.")
    p.add_argument("--baud", type=int, default=lidar_io.BAUD)
    p.add_argument("--rotations", type=int, default=CAPTURE_ROTATIONS,
                   help=f"rotations to stack per sensor (default {CAPTURE_ROTATIONS})")
    p.add_argument("--span", type=float, default=JIG_SPAN_M, metavar="M",
                   help="the printed jig's post spacing in metres "
                        f"(default {JIG_SPAN_M})")
    p.add_argument("--no-jig", action="store_true",
                   help="don't look for the jig; match single clumps, so a "
                        "drinks can against each sensor will do")
    p.add_argument("--marker-radius", type=float, metavar="M",
                   help="how fat the markers are, in metres, if you know "
                        "(default: half the width each sensor measured)")
    p.add_argument("--range", nargs=2, type=float, metavar=("MIN", "MAX"),
                   default=(MIN_SEP_M, MAX_SEP_M),
                   help="how far apart the sensors could possibly be, in metres")
    p.add_argument("--no-polish", action="store_true",
                   help="skip the ICP refinement and keep the raw sighting")
    p.add_argument("--save", action="store_true", help="save without asking")
    p.add_argument("--no-save", action="store_true", help="never save")
    args = p.parse_args()

    min_sep, max_sep = float(args.range[0]), float(args.range[1])

    ports = args.port or lidar_io.find_ports()
    if len(ports) < 2:
        print("need two lidars plugged in; found: " + (", ".join(ports) or "none"))
        return 1

    print("Stand clear - the room has to be still.")
    if args.no_jig:
        print("Each sensor needs something upright 5-10 cm across standing against "
              "it,\nand tall enough to cross the height the other sensor scans at.\n")
    else:
        print("Each sensor needs its printed jig on (see hardware/), with the arrow\n"
              "pointing at the other sensor so the posts stand out to the sides.\n")

    scans, serials = [], []
    for port in ports:
        print(f"sensor {len(scans) + 1} of {len(ports)}:")
        try:
            points, serial = capture(port, args.baud, args.rotations)
        except Exception as exc:
            print(f"  could not read {port}: {exc}")
            return 1
        scans.append(points)
        serials.append(serial)
    print()

    saved = load_poses()
    anchor = (0.0, 0.0, 0.0)
    if serials[0] and serials[0] in saved:
        v = saved[serials[0]]
        anchor = (float(v["x"]), float(v["y"]), float(v["rot"]))
        print(f"anchor: sensor 1 keeps its saved place "
              f"({anchor[0]:+.3f}, {anchor[1]:+.3f}) m, {anchor[2]:+.2f}deg")
    else:
        print("anchor: sensor 1 is the origin, facing up the map")

    entries = [(serials[0], anchor, ports[0], "A")]
    failed = False
    for n in range(1, len(scans)):
        name = chr(ord("A") + n)
        print(f"\nsensor {n + 1} ({name}, {ports[n]}):")
        result = calibrate_pair(scans[0], scans[n], anchor, args.marker_radius,
                                min_sep, max_sep,
                                span=None if args.no_jig else args.span)
        print("  " + result.report().replace("\n", "\n  "))
        if not result.ok:
            failed = True
            continue
        pose = result.pose
        if not args.no_polish:
            pose, note = polish(scans[n], scans[0], anchor, pose)
            print(f"  {note}")
        print(f"  final: ({pose[0]:+.3f}, {pose[1]:+.3f}) m, turned {pose[2]:+.2f}deg")
        entries.append((serials[n], pose, ports[n], name))

    if len(entries) < 2:
        print("\nnothing to save.")
        return 1

    if args.no_save:
        return 1 if failed else 0

    if not args.save:
        if os.path.exists(ALIGN_FILE):
            print(f"\n{os.path.basename(ALIGN_FILE)} already exists and will be "
                  "overwritten for these sensors.")
        answer = input("\nsave this alignment? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("not saved.")
            return 1 if failed else 0

    print(save_poses(entries))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
