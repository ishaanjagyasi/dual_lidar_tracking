# Finding a person on the carpet and following the point midway between their
# two legs.
#
# Works whether the sensors are low enough to see shoes or high enough to see
# shins: the logic only cares that there are one or two blobs moving about, not
# what part of a leg they are.
#
# Three steps:
#
#   background   with the carpet empty, remember how far away the nearest
#                static thing is at every angle. Anything closer than that
#                later on is a person.
#   blobs        group the leftover points. Each blob is a leg.
#   midpoint     two blobs -> the point between them. One blob -> that leg plus
#                the offset we last measured between it and the middle, so the
#                point keeps moving instead of freezing.
#
# A leg in mid-stride lifts clear of the scan slice and disappears, so seeing
# only one is normal while walking, not an error.

import math
import time

import numpy as np
from scipy.spatial import cKDTree

# finding people
BACKGROUND_BINS = 360         # one degree each: readings are ~0.8 deg apart, so
                              # finer bins would leave gaps with nothing in them
BACKGROUND_QUANTILE = 5       # the near edge of the static clutter, in percent
FOREGROUND_MARGIN_M = 0.08    # must be this much nearer than the background
CLUSTER_EPS_M = 0.08          # points this close together are the same leg
MIN_BLOB_POINTS = 3
MIN_BLOB_SIZE_M = 0.02        # smaller than this is noise
MAX_BLOB_SIZE_M = 0.45        # bigger than this is furniture, not a leg

# putting legs together into a person
MAX_LEG_GAP_M = 0.90          # two legs further apart than this aren't one person
LEGS_TOGETHER_M = 0.22        # a single blob wider than this is both legs at once
SEARCH_RADIUS_M = 1.20        # how far from where they were to look

# carrying on when a leg or the whole person disappears
STALE_AFTER_S = 0.15          # a sighting older than this counts as a gap
PREDICT_S = 0.30              # keep moving at the last speed for this long
HOLD_S = 1.00                 # then stand still, then give up
SMOOTHING = 0.35              # 0 = jumpy and instant, 1 = smooth and laggy
MAX_SPEED_MS = 4.0            # ignore jumps faster than a person can move

BOTH = "both legs"
TOGETHER = "legs together"
ONE = "one leg"
PREDICTED = "predicted"
HELD = "held"
LOST = "lost"


def _fill_gaps(values):
    """Angles that never got a reading borrow from their neighbours. Without
    this, anything landing in an empty bin looks like a person."""
    n = len(values)
    if not np.isfinite(values).any():
        return values

    def sweep(order):
        out = values.copy()
        last = None
        for _ in range(2):                 # twice round, so the ends wrap
            for i in order:
                if np.isfinite(out[i]):
                    last = out[i]
                elif last is not None:
                    out[i] = last
        return out

    # take whichever neighbour is nearer, so an unknown angle errs towards
    # calling things scenery rather than inventing a person
    return np.minimum(sweep(range(n)), sweep(range(n - 1, -1, -1)))


class Background:
    """How far away the static scenery is, at every angle, for each sensor."""

    def __init__(self, bins=BACKGROUND_BINS, margin_m=FOREGROUND_MARGIN_M):
        self.bins = bins
        self.margin = margin_m
        self._samples = {}
        self.distance = {}
        self.rotations = 0

    def add(self, sensor_name, scan):
        """Feed it rotations taken with the carpet empty."""
        bins = self._samples.setdefault(sensor_name, [[] for _ in range(self.bins)])
        for angle, dist_mm, _q in scan:
            bins[int(angle / 360.0 * self.bins) % self.bins].append(dist_mm / 1000.0)
        self.rotations += 1

    def finish(self):
        for name, bins in self._samples.items():
            out = np.full(self.bins, np.inf)
            for i, seen in enumerate(bins):
                if seen:
                    out[i] = np.percentile(seen, BACKGROUND_QUANTILE)
            self.distance[name] = _fill_gaps(out)
        self._samples = {}
        return self.ready

    @property
    def ready(self):
        return bool(self.distance)

    def foreground(self, sensor_name, scan):
        """Which readings are nearer than the scenery, so probably a person."""
        if not len(scan):
            return np.zeros(0, dtype=bool)
        known = self.distance.get(sensor_name)
        if known is None:
            return np.ones(len(scan), dtype=bool)
        angles = np.fromiter((p[0] for p in scan), float, len(scan))
        dists = np.fromiter((p[1] for p in scan), float, len(scan)) / 1000.0
        idx = (angles / 360.0 * self.bins).astype(int) % self.bins
        return dists < known[idx] - self.margin


class Blob:
    """A clump of points: one leg, or both when they're close together."""

    def __init__(self, points):
        self.points = points
        self.centre = points.mean(axis=0)
        self.count = len(points)
        spread = points - self.centre
        self.size = float(2.0 * np.sqrt((spread ** 2).sum(axis=1).max())) if len(points) > 1 else 0.0

    def __repr__(self):
        return f"Blob({self.centre[0]:.2f},{self.centre[1]:.2f} n={self.count} {self.size*100:.0f}cm)"


def find_blobs(points, eps=CLUSTER_EPS_M, min_points=MIN_BLOB_POINTS):
    """Group nearby points, then throw away anything the wrong size for a leg."""
    points = np.asarray(points, dtype=float)
    if len(points) < min_points:
        return []

    tree = cKDTree(points)
    seen = np.zeros(len(points), dtype=bool)
    blobs = []
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
        if len(group) < min_points:
            continue
        blob = Blob(points[group])
        if MIN_BLOB_SIZE_M <= blob.size <= MAX_BLOB_SIZE_M:
            blobs.append(blob)
    return blobs


class Tracker:
    """Follows the point midway between a person's two legs."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.position = None         # the smoothed answer, metres
        self.raw = None              # before smoothing
        self.velocity = np.zeros(2)
        self.legs = None             # where each leg was last seen
        self.state = LOST
        self.last_seen = None        # when a leg was last actually seen
        self.last_update = None
        self.blobs = []

    @property
    def age(self):
        """How long since a leg was actually seen, in seconds."""
        if self.last_seen is None:
            return float("inf")
        return max(0.0, (self.last_update or self.last_seen) - self.last_seen)

    @property
    def confident(self):
        return self.state in (BOTH, TOGETHER, ONE)

    def tick(self, t):
        """Time passing with no new readings. Call this on frames where the
        sensors haven't produced a fresh rotation, so the clock keeps running
        without the same scan being counted twice."""
        previous = self.last_update
        self.last_update = t
        if self.last_seen is None or t - self.last_seen <= STALE_AFTER_S:
            return self.position
        self._coast(t, previous)
        return self.position

    def update(self, t, blobs):
        """A fresh rotation's worth of blobs."""
        previous = self.last_update
        self.last_update = t
        self.blobs = blobs
        chosen = self._pick(blobs)

        if chosen is None:
            self._coast(t, previous)
            return self.position

        midpoint, state, legs = chosen
        if self.position is not None and self.last_seen is not None:
            gap = t - self.last_seen
            if gap > 1e-6 and float(np.hypot(*(midpoint - self.raw))) / gap > MAX_SPEED_MS:
                # too fast to be a person; sit tight rather than teleport
                self._coast(t, previous)
                return self.position

        if self.raw is not None and self.last_seen is not None and t > self.last_seen:
            self.velocity = (midpoint - self.raw) / (t - self.last_seen)

        self.raw = midpoint
        self.position = (midpoint if self.position is None
                         else self.position + (midpoint - self.position) * (1.0 - SMOOTHING))
        self.legs = legs
        self.state = state
        self.last_seen = t
        return self.position

    # ------------------------------------------------------------------ inside

    def _pick(self, blobs):
        """Work out the midpoint from whatever blobs we can see."""
        if not blobs:
            return None

        near = blobs
        if self.position is not None:
            near = [b for b in blobs
                    if float(np.hypot(*(b.centre - self.position))) <= SEARCH_RADIUS_M]
            if not near:
                near = blobs if self.state == LOST else []
        if not near:
            return None

        if len(near) >= 2:
            pair = self._closest_pair(near)
            if pair is not None:
                a, b = pair
                return (a.centre + b.centre) / 2.0, BOTH, (a.centre, b.centre)

        one = min(near, key=lambda b: 0.0 if self.position is None
                  else float(np.hypot(*(b.centre - self.position))))

        if one.size >= LEGS_TOGETHER_M:
            half = np.array([one.size / 4.0, 0.0])
            return one.centre, TOGETHER, (one.centre - half, one.centre + half)

        if self.legs is not None:
            # which leg is this, and where was the middle relative to it?
            first, second = self.legs
            d_first = float(np.hypot(*(one.centre - first)))
            d_second = float(np.hypot(*(one.centre - second)))
            if min(d_first, d_second) <= SEARCH_RADIUS_M:
                if d_first <= d_second:
                    other = one.centre + (second - first)
                    legs = (one.centre, other)
                else:
                    other = one.centre + (first - second)
                    legs = (other, one.centre)
                return (legs[0] + legs[1]) / 2.0, ONE, legs

        # nothing to go on yet: the one leg is the best guess we have
        return one.centre, ONE, (one.centre, one.centre)

    def _closest_pair(self, blobs):
        best, best_gap = None, MAX_LEG_GAP_M
        anchor = self.position
        for i in range(len(blobs)):
            for j in range(i + 1, len(blobs)):
                gap = float(np.hypot(*(blobs[i].centre - blobs[j].centre)))
                if gap > MAX_LEG_GAP_M:
                    continue
                score = gap
                if anchor is not None:
                    middle = (blobs[i].centre + blobs[j].centre) / 2.0
                    score = float(np.hypot(*(middle - anchor)))
                if best is None or score < best_gap:
                    best, best_gap = (blobs[i], blobs[j]), score
        return best

    def _coast(self, t, previous):
        """Nothing visible: keep going briefly, then stand still, then give up."""
        if self.position is None or self.last_seen is None:
            self.state = LOST
            return
        gap = t - self.last_seen
        if gap <= PREDICT_S:
            step = t - previous if previous is not None else 0.0
            self.position = self.position + self.velocity * step
            self.state = PREDICTED
        elif gap <= HOLD_S:
            self.state = HELD
        else:
            self.state = LOST
            self.position = None
            self.raw = None
            self.legs = None
            self.velocity = np.zeros(2)
