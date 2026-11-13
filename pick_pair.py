# Calibrate by pointing at the other sensor yourself. Live.
#
#   python3 pick_pair.py
#
# calibrate_pair.py finds the jig's two posts on its own. When it can't - too
# far, too cluttered, or the posts merging with the sensor's own case at range
# - you can still see the other sensor in the scan perfectly well. So: two
# panels, one per sensor, both running live. Click where the OTHER sensor is in
# each. Those are the same two sightings the automatic version works from, and
# every line after the click is shared with it.
#
# Both panels update continuously. Wave a hand next to one sensor and watch
# which blob moves in the other's panel - that is the quickest way to settle
# which thing is which. What you see is the last few seconds of rotations
# stacked on top of each other, because one rotation on its own puts readings
# 38 mm apart at 3 m and a 25 mm post would flicker in and out. Moving things
# smear into a trail, which is exactly what makes them easy to spot.
#
# Clicking snaps to what is actually there:
#
#   a jig's two posts   if a pair the right distance apart lies near the click,
#                       the midpoint between them is used. That is the other
#                       sensor's spin axis exactly, so it is the best case.
#   one clump           otherwise the nearest clump, pushed out by half its
#                       width, because the laser stops at the near face.
#   the bare click      if there is nothing near, your click is used as-is.
#
# The status line always says which of the three, so a sloppy click is never
# quietly treated as a precise one.
#
#   click    pick, in either panel      BACKSPACE  clear that panel
#   SPACE    freeze / unfreeze          N          snapping on / off
#   P        polish with ICP            S          save        ESC  quit
#   wheel    zoom the panel under the mouse
#
# Dashed lines: every sensor sees its own two posts at about 65 mm, and the
# arrow points at right angles to them. So the other sensor sits somewhere on
# one of those two lines - which is where to look.

import argparse
import json
import math
import os
import threading
import time
from collections import deque

import numpy as np

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

import align
import calibrate_pair as cal
import lidar_io

W, H = 1500, 880
PANEL_H = 700
BG = (16, 18, 24)
PANEL_BG = (22, 25, 33)
RING = (34, 38, 48)
EDGE = (45, 50, 62)
TEXT = (226, 231, 240)
DIM = (132, 142, 158)
OK = (90, 215, 140)
WARN = (247, 184, 72)
BAD = (240, 100, 110)
OLD = (70, 96, 118)
NEW = (150, 205, 240)
PICK = (250, 95, 165)
POST = (240, 225, 120)
SENSOR = (95, 200, 255)
GUIDE = (120, 95, 60)

SNAP_M = 0.30
STACK = 30            # rotations held on screen, about three seconds
REFRESH_S = 0.6       # how often the blob finder re-runs, in its own thread


class Reader(threading.Thread):
    """Keeps one sensor spinning and holds the last few seconds of rotations."""

    def __init__(self, port, stack=STACK):
        super().__init__(daemon=True)
        self.port = port
        self.lock = threading.Lock()
        self.turns = deque(maxlen=stack)
        self.serial = None
        self.error = None
        self.rotations = 0
        self.stop = threading.Event()

    def run(self):
        lidar = None
        try:
            lidar, info, _health = lidar_io.open_lidar(self.port, quiet=True)
            self.serial = (info or {}).get("serialnumber")
            for scan in lidar_io.rotations(lidar):
                if self.stop.is_set():
                    break
                with self.lock:
                    self.turns.append(scan)
                    self.rotations += 1
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
        finally:
            if lidar is not None:
                lidar_io.close_lidar(lidar)

    def snapshot(self):
        """Everything on screen, and the newest rotation on its own."""
        with self.lock:
            if not self.turns:
                return [], []
            return [p for t in self.turns for p in t], list(self.turns[-1])


def arrow_axis(scan):
    """Which way the jig's arrow points, from the sensor's own two posts.

    Every sensor sees its own posts at about 65 mm. They stand at right angles
    to the arrow, so the arrow - and with it the other sensor, if the arrows
    are aimed at each other - lies along the line at right angles to them. That
    is the line to look along. Returns both directions, since from here there
    is no telling which end the arrow is on.
    """
    a = np.array([p[0] for p in scan]); d = np.array([p[1] for p in scan]) / 1000
    own = a[(d > 0.03) & (d < 0.12)]
    if len(own) < 6:
        return []
    r = np.radians(own)
    # fold both posts onto one direction by doubling the angle
    mean2 = math.degrees(math.atan2(np.sin(2 * r).mean(), np.cos(2 * r).mean())) / 2
    return [(mean2 + 90) % 360, (mean2 - 90) % 360]


class Panel:
    def __init__(self, name, rect, reader):
        self.name = name
        self.rect = pygame.Rect(rect)
        self.reader = reader
        self.surface = pygame.Surface((self.rect.w, self.rect.h))
        self.scan = []
        self.local = np.zeros((0, 2))
        self.fresh = np.zeros((0, 2))
        self.blobs = []
        self.jigs = []
        self.scale = 0.0
        self.pick = None          # (x, y) metres, this sensor's own frame
        self.how = ""
        self.frozen = False
        self.axis = []            # bearings the arrow could point along
        self._work = threading.Thread(target=self._find, daemon=True)
        self._stop = threading.Event()
        self._work.start()

    def _find(self):
        """Clustering is far too slow for the draw loop, so it lives here."""
        while not self._stop.is_set():
            scan = self.scan
            if len(scan) > 200:
                try:
                    blobs = cal.candidate_blobs(scan, clear=0.0)
                    jigs = cal.find_jigs(scan)
                    self.blobs, self.jigs = blobs, jigs
                    self.axis = arrow_axis(scan)
                except Exception:
                    pass
            time.sleep(REFRESH_S)

    def close(self):
        self._stop.set()

    def pull(self):
        if self.frozen:
            return
        scan, newest = self.reader.snapshot()
        if not scan:
            return
        self.scan = scan
        self.local = align.polar_to_local(scan)
        self.fresh = align.polar_to_local(newest)
        if self.scale <= 0 and len(self.local):
            reach = float(np.percentile(np.hypot(*self.local.T), 92)) or 1.0
            self.scale = max(18.0, (min(self.rect.w, self.rect.h) * 0.42) / reach)

    def to_screen(self, x, y):
        return (int(self.rect.w / 2 + x * self.scale),
                int(self.rect.h / 2 - y * self.scale))

    def to_world(self, sx, sy):
        return ((sx - self.rect.x - self.rect.w / 2) / self.scale,
                (self.rect.y + self.rect.h / 2 - sy) / self.scale)

    def choose(self, sx, sy, snap=True):
        wx, wy = self.to_world(sx, sy)
        here = np.array([wx, wy])
        if not snap:
            self.pick, self.how = (wx, wy), "exactly where you clicked"
            return
        best = None
        for s in self.jigs:
            r = math.radians(s.bearing)
            mid = np.array([s.distance * math.sin(r), s.distance * math.cos(r)])
            d = float(np.hypot(*(mid - here)))
            if d <= SNAP_M and (best is None or d < best[0]):
                out = s.centre_distance()
                best = (d, (out * math.sin(r), out * math.cos(r)),
                        f"the jig's two posts, {s.span*1000:.0f} mm apart "
                        f"(+{(out - s.distance)*1000:.0f} mm to the middle)")
        if best is None:
            for b in self.blobs:
                d = float(np.hypot(*(b.centre - here)))
                if d <= SNAP_M and (best is None or d < best[0]):
                    r = math.hypot(*b.centre)
                    out = r + b.size / 2.0
                    k = out / r if r else 1.0
                    best = (d, (b.centre[0] * k, b.centre[1] * k),
                            f"one clump {b.size*1000:.0f} mm across, {b.count} "
                            f"points (+{b.size/2*1000:.0f} mm to the middle)")
        if best is None:
            self.pick, self.how = (wx, wy), "nothing near it - taken as clicked"
        else:
            self.pick, self.how = best[1], best[2]

    @property
    def bearing(self):
        return cal.bearing_of(self.pick) if self.pick else None

    @property
    def distance(self):
        return float(math.hypot(*self.pick)) if self.pick else None

    def _plot(self, pts, colour):
        if not len(pts):
            return
        sx = (self.rect.w / 2 + pts[:, 0] * self.scale).astype(int)
        sy = (self.rect.h / 2 - pts[:, 1] * self.scale).astype(int)
        arr = pygame.surfarray.pixels3d(self.surface)
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):     # 2x2, so posts show
            x, y = sx + dx, sy + dy
            keep = (x >= 0) & (x < self.rect.w) & (y >= 0) & (y < self.rect.h)
            arr[x[keep], y[keep]] = colour
        del arr

    def draw(self, screen, font, small):
        self.surface.fill(PANEL_BG)
        cx, cy = self.rect.w // 2, self.rect.h // 2
        for ring in range(1, 12):
            rr = int(ring * self.scale)
            if rr > max(self.rect.w, self.rect.h):
                break
            pygame.draw.circle(self.surface, RING, (cx, cy), rr, 1)
            self.surface.blit(small.render(f"{ring} m", True, (70, 78, 92)),
                              (cx + 4, cy - rr - 13))
        for b in self.axis:
            r = math.radians(b)
            reach = max(self.rect.w, self.rect.h)
            end = (int(cx + reach * math.sin(r)), int(cy - reach * math.cos(r)))
            for k in range(0, reach, 14):           # dashed
                p0 = (int(cx + k * math.sin(r)), int(cy - k * math.cos(r)))
                p1 = (int(cx + (k + 7) * math.sin(r)), int(cy - (k + 7) * math.cos(r)))
                pygame.draw.line(self.surface, GUIDE, p0, p1, 1)
        self._plot(self.local, OLD)
        self._plot(self.fresh, NEW)

        for s in self.jigs:
            r = math.radians(s.bearing)
            pygame.draw.circle(self.surface, POST,
                               self.to_screen(s.distance * math.sin(r),
                                              s.distance * math.cos(r)), 9, 1)
        pygame.draw.circle(self.surface, SENSOR, (cx, cy), 7)
        pygame.draw.circle(self.surface, SENSOR, (cx, cy), 13, 1)

        if self.pick:
            p = self.to_screen(*self.pick)
            pygame.draw.line(self.surface, PICK, (cx, cy), p, 1)
            pygame.draw.circle(self.surface, PICK, p, 11, 2)
            pygame.draw.line(self.surface, PICK, (p[0] - 17, p[1]), (p[0] + 17, p[1]))
            pygame.draw.line(self.surface, PICK, (p[0], p[1] - 17), (p[0], p[1] + 17))

        screen.blit(self.surface, self.rect.topleft)
        pygame.draw.rect(screen, EDGE, self.rect, 1)

        head = f"sensor {self.name}  {os.path.basename(self.reader.port)}"
        if self.frozen:
            head += "   [FROZEN]"
        screen.blit(font.render(head, True, WARN if self.frozen else TEXT),
                    (self.rect.x + 12, self.rect.y + 9))
        state = (f"{self.reader.rotations} turns" if not self.reader.error
                 else self.reader.error)
        screen.blit(small.render(state, True, DIM),
                    (self.rect.right - 150, self.rect.y + 12))
        if self.pick:
            screen.blit(small.render(
                f"{self.distance:.3f} m at {self.bearing:+.2f}deg - {self.how}",
                True, OK), (self.rect.x + 12, self.rect.bottom - 22))
        else:
            screen.blit(small.render(
                "click the other sensor  (wave a hand by it to find it)",
                True, WARN), (self.rect.x + 12, self.rect.bottom - 22))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", action="append", metavar="DEV")
    p.add_argument("--stack", type=int, default=STACK,
                   help="rotations held on screen (default %(default)s)")
    args = p.parse_args()

    ports = args.port or lidar_io.find_ports()
    if len(ports) < 2:
        print("need two lidars plugged in; found: " + (", ".join(ports) or "none"))
        return 1
    ports = ports[:2]

    readers = [Reader(port, args.stack) for port in ports]
    for r in readers:
        r.start()

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("pick the other sensor - live")
    font = pygame.font.SysFont("menlo,dejavusansmono,monospace", 17)
    small = pygame.font.SysFont("menlo,dejavusansmono,monospace", 13)
    clock = pygame.time.Clock()

    pad = 12
    pw = (W - 3 * pad) // 2
    panels = [Panel("A", (pad, pad, pw, PANEL_H), readers[0]),
              Panel("B", (2 * pad + pw, pad, pw, PANEL_H), readers[1])]

    snap = True
    pose = None
    note = "both panels are live - wave a hand next to one sensor to find it"
    saved = ""
    running = True

    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_SPACE:
                    frozen = not panels[0].frozen
                    for pan in panels:
                        pan.frozen = frozen
                    note = ("frozen - the picture will hold still while you click"
                            if frozen else "live again")
                elif e.key == pygame.K_n:
                    snap = not snap
                    note = f"snapping {'on' if snap else 'off'}"
                elif e.key == pygame.K_BACKSPACE:
                    mx, my = pygame.mouse.get_pos()
                    for pan in panels:
                        if pan.rect.collidepoint(mx, my):
                            pan.pick, pan.how = None, ""
                    pose, saved = None, ""
                elif e.key == pygame.K_p and pose:
                    pose, note = cal.polish(panels[1].scan, panels[0].scan,
                                            (0.0, 0.0, 0.0), pose)
                    saved = ""
                elif e.key == pygame.K_s and pose:
                    keep = {}
                    if os.path.exists(cal.ALIGN_FILE):
                        try:
                            keep = json.load(open(cal.ALIGN_FILE))
                        except Exception:
                            keep = {}
                    for n, (r, pz) in enumerate(zip(readers,
                                                    ((0.0, 0.0, 0.0), pose))):
                        if r.serial:
                            keep[r.serial] = {"x": pz[0], "y": pz[1], "rot": pz[2],
                                              "port_last_seen": r.port,
                                              "name": "AB"[n]}
                    json.dump(keep, open(cal.ALIGN_FILE, "w"), indent=2)
                    saved = f"saved to {os.path.basename(cal.ALIGN_FILE)}"
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1:
                    for pan in panels:
                        if pan.rect.collidepoint(e.pos):
                            pan.choose(*e.pos, snap=snap)
                            pose, saved = None, ""
                elif e.button in (4, 5):
                    for pan in panels:
                        if pan.rect.collidepoint(e.pos):
                            pan.scale *= 1.15 if e.button == 4 else 1 / 1.15
                            pan.scale = max(8.0, min(600.0, pan.scale))

        for pan in panels:
            pan.pull()

        a, b = panels
        if a.pick and b.pick and pose is None:
            pose = cal.solve_pose((0.0, 0.0, 0.0), a.bearing, b.bearing,
                                  (a.distance + b.distance) / 2.0)

        screen.fill(BG)
        for pan in panels:
            pan.draw(screen, font, small)

        y = PANEL_H + 2 * pad
        if a.pick and b.pick:
            off = abs(a.distance - b.distance)
            col = OK if off < 0.08 else (WARN if off < 0.20 else BAD)
            lines = [(f"A says {a.distance:.3f} m, B says {b.distance:.3f} m "
                      f"- they differ by {off*1000:.0f} mm", col),
                     (f"B is at ({pose[0]:+.3f}, {pose[1]:+.3f}) m, turned "
                      f"{pose[2]:+.2f}deg, {math.hypot(*pose[:2]):.3f} m away", TEXT)]
            if off >= 0.20:
                lines.append(("Both are measuring the same gap, so those should "
                              "match. They don't - one click is on something else.",
                              BAD))
            lines.append((note, DIM))
            if saved:
                lines.append((saved, OK))
        else:
            lines = [("Click the other sensor in each panel. It sits on one of the "
                      "dashed lines - that is the arrow's direction, worked out "
                      "from this sensor's own posts.", TEXT),
                     ("Yellow rings are pairs that look like a jig.", DIM),
                     (note, DIM)]
        for text, col in lines:
            screen.blit(font.render(text, True, col), (pad + 4, y))
            y += 23

        screen.blit(small.render(
            "click pick   BACKSPACE clear   SPACE freeze   N snap on/off   "
            "P polish   S save   wheel zoom   ESC quit", True, DIM),
            (pad + 4, H - 20))
        pygame.display.flip()
        clock.tick(45)

    for pan in panels:
        pan.close()
    for r in readers:
        r.stop.set()
    for r in readers:
        r.join(timeout=2.0)
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
