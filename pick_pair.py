# Calibrate by pointing at the other sensor yourself.
#
#   python3 pick_pair.py
#
# calibrate_pair.py finds the jig's two posts on its own. When it can't - too
# far, too cluttered, the posts merging with the case at range - you can still
# see the other sensor in the scan perfectly well. So: two panels, one per
# sensor, each showing what that sensor sees. Click where the OTHER sensor is
# in each. That is the same pair of sightings the automatic version works from,
# and the arithmetic afterwards is identical.
#
# Clicking snaps to what is actually there, in this order:
#
#   a jig's two posts   if a pair the right distance apart lies near the click,
#                       the midpoint between them is used. That point is the
#                       other sensor's spin axis exactly, so this is the best
#                       case and worth aiming for.
#   one clump           otherwise the nearest clump of points, pushed out by
#                       half its width because the laser stops at the near
#                       face, not the middle.
#   the bare click      if there is nothing near, your click is taken as-is.
#
# The status line always says which of the three it used, so a sloppy click is
# never silently treated as a precise one.
#
#   click        pick, in either panel        BACKSPACE  clear that panel
#   N            snapping on / off            R          read the sensors again
#   P            polish with ICP              S          save    ESC  quit
#   wheel        zoom the panel under the mouse

import argparse
import json
import math
import os

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
EDGE = (45, 50, 62)
TEXT = (226, 231, 240)
DIM = (132, 142, 158)
OK = (90, 215, 140)
WARN = (247, 184, 72)
BAD = (240, 100, 110)
PT = (120, 160, 190)
PICK = (250, 95, 165)
POST = (240, 225, 120)
SENSOR = (95, 200, 255)

SNAP_M = 0.30


class Panel:
    def __init__(self, name, rect):
        self.name = name
        self.rect = pygame.Rect(rect)
        self.scan = []
        self.local = np.zeros((0, 2))
        self.blobs = []
        self.jigs = []
        self.scale = 90.0
        self.pick = None          # (x, y) metres, in this sensor's own frame
        self.how = ""

    def load(self, scan):
        self.scan = scan
        self.local = align.polar_to_local(scan)
        self.blobs = cal.candidate_blobs(scan, clear=0.0)
        self.jigs = cal.find_jigs(scan)
        if len(self.local):
            reach = float(np.percentile(np.hypot(*self.local.T), 92)) or 1.0
            self.scale = max(18.0, (min(self.rect.w, self.rect.h) * 0.42) / reach)

    def to_screen(self, x, y):
        return (int(self.rect.centerx + x * self.scale),
                int(self.rect.centery - y * self.scale))

    def to_world(self, sx, sy):
        return ((sx - self.rect.centerx) / self.scale,
                (self.rect.centery - sy) / self.scale)

    def choose(self, sx, sy, snap=True):
        """Turn a click into a sighting, snapping to real geometry if asked."""
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
                            f"one clump {b.size*1000:.0f} mm across, "
                            f"{b.count} points (+{b.size/2*1000:.0f} mm to the middle)")
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

    def draw(self, surf, font, small, picked_colour):
        pygame.draw.rect(surf, PANEL_BG, self.rect)
        pygame.draw.rect(surf, EDGE, self.rect, 1)
        old = surf.get_clip()
        surf.set_clip(self.rect)

        for ring in range(1, 9):
            rr = int(ring * self.scale)
            if rr > max(self.rect.w, self.rect.h):
                break
            pygame.draw.circle(surf, (34, 38, 48), self.rect.center, rr, 1)
            surf.blit(small.render(f"{ring} m", True, (70, 78, 92)),
                      (self.rect.centerx + 4, self.rect.centery - rr - 13))

        for x, y in self.local:
            sx, sy = self.to_screen(x, y)
            if self.rect.collidepoint(sx, sy):
                surf.set_at((sx, sy), PT)

        for s in self.jigs:
            r = math.radians(s.bearing)
            p = self.to_screen(s.distance * math.sin(r), s.distance * math.cos(r))
            pygame.draw.circle(surf, POST, p, 9, 1)

        pygame.draw.circle(surf, SENSOR, self.rect.center, 7)
        pygame.draw.circle(surf, SENSOR, self.rect.center, 13, 1)

        if self.pick:
            p = self.to_screen(*self.pick)
            pygame.draw.line(surf, picked_colour, self.rect.center, p, 1)
            pygame.draw.circle(surf, picked_colour, p, 11, 2)
            pygame.draw.line(surf, picked_colour, (p[0] - 17, p[1]), (p[0] + 17, p[1]))
            pygame.draw.line(surf, picked_colour, (p[0], p[1] - 17), (p[0], p[1] + 17))

        surf.set_clip(old)
        surf.blit(font.render(f"sensor {self.name}", True, TEXT),
                  (self.rect.x + 12, self.rect.y + 9))
        if self.pick:
            surf.blit(small.render(
                f"{self.distance:.3f} m at {self.bearing:+.2f}deg - {self.how}",
                True, OK), (self.rect.x + 12, self.rect.bottom - 22))
        else:
            surf.blit(small.render("click the other sensor", True, WARN),
                      (self.rect.x + 12, self.rect.bottom - 22))


def load_poses(path):
    if not os.path.exists(path):
        return {}
    try:
        return json.load(open(path))
    except Exception:
        return {}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", action="append", metavar="DEV")
    p.add_argument("--rotations", type=int, default=30)
    args = p.parse_args()

    ports = args.port or lidar_io.find_ports()
    if len(ports) < 2:
        print("need two lidars plugged in; found: " + (", ".join(ports) or "none"))
        return 1
    ports = ports[:2]

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("pick the other sensor")
    font = pygame.font.SysFont("menlo,dejavusansmono,monospace", 17)
    small = pygame.font.SysFont("menlo,dejavusansmono,monospace", 13)
    clock = pygame.time.Clock()

    pad = 12
    pw = (W - 3 * pad) // 2
    panels = [Panel("A", (pad, pad, pw, PANEL_H)),
              Panel("B", (2 * pad + pw, pad, pw, PANEL_H))]
    serials = [None, None]

    def grab():
        screen.fill(BG)
        screen.blit(font.render("reading both sensors...", True, TEXT), (pad + 10, pad + 10))
        pygame.display.flip()
        for n, port in enumerate(ports):
            pts, serial = cal.capture(port, rotations=args.rotations, quiet=True)
            serials[n] = serial
            panels[n].load(pts)

    grab()

    snap = True
    pose = None
    note = "click the other sensor in each panel"
    saved = ""

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); return 0
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    pygame.quit(); return 0
                if e.key == pygame.K_n:
                    snap = not snap
                    note = f"snapping {'on' if snap else 'off'}"
                if e.key == pygame.K_BACKSPACE:
                    mx, my = pygame.mouse.get_pos()
                    for pan in panels:
                        if pan.rect.collidepoint(mx, my):
                            pan.pick, pan.how = None, ""
                    pose = None; saved = ""
                if e.key == pygame.K_r:
                    grab(); pose = None; saved = ""
                    note = "read again"
                if e.key == pygame.K_p and pose:
                    refined, msg = cal.polish(panels[1].scan, panels[0].scan,
                                              (0.0, 0.0, 0.0), pose)
                    pose, note, saved = refined, msg, ""
                if e.key == pygame.K_s and pose:
                    path = cal.ALIGN_FILE
                    keep = load_poses(path)
                    if serials[0]:
                        keep[serials[0]] = {"x": 0.0, "y": 0.0, "rot": 0.0,
                                            "port_last_seen": ports[0], "name": "A"}
                    if serials[1]:
                        keep[serials[1]] = {"x": pose[0], "y": pose[1], "rot": pose[2],
                                            "port_last_seen": ports[1], "name": "B"}
                    json.dump(keep, open(path, "w"), indent=2)
                    saved = f"saved to {os.path.basename(path)}"
            if e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1:
                    for pan in panels:
                        if pan.rect.collidepoint(e.pos):
                            pan.choose(*e.pos, snap=snap)
                            pose = None; saved = ""
                elif e.button in (4, 5):
                    for pan in panels:
                        if pan.rect.collidepoint(e.pos):
                            pan.scale *= 1.15 if e.button == 4 else 1 / 1.15
                            pan.scale = max(8.0, min(600.0, pan.scale))

        a, b = panels
        if a.pick and b.pick and pose is None:
            da, db = a.distance, b.distance
            sep = (da + db) / 2.0
            pose = cal.solve_pose((0.0, 0.0, 0.0), a.bearing, b.bearing, sep)

        screen.fill(BG)
        for pan in panels:
            pan.draw(screen, font, small, PICK)

        y = PANEL_H + 2 * pad
        if panels[0].pick and panels[1].pick:
            da, db = panels[0].distance, panels[1].distance
            off = abs(da - db)
            col = OK if off < 0.08 else (WARN if off < 0.20 else BAD)
            lines = [
                (f"A says {da:.3f} m, B says {db:.3f} m - they differ by "
                 f"{off*1000:.0f} mm", col),
                (f"B is at ({pose[0]:+.3f}, {pose[1]:+.3f}) m, turned "
                 f"{pose[2]:+.2f}deg, {math.hypot(pose[0], pose[1]):.3f} m away", TEXT),
            ]
            if off >= 0.20:
                lines.append(("Both are measuring the same gap, so those two numbers "
                              "should match. They don't, so one of the clicks is on "
                              "something else.", BAD))
            lines.append((note, DIM))
            if saved:
                lines.append((saved, OK))
        else:
            lines = [("Click the other sensor in each panel. Yellow rings are pairs "
                      "that look like a jig.", TEXT),
                     (note, DIM)]
        for text, col in lines:
            screen.blit(font.render(text, True, col), (pad + 4, y))
            y += 23

        screen.blit(small.render(
            "click pick   BACKSPACE clear   N snap on/off   R read again   "
            "P polish with ICP   S save   wheel zoom   ESC quit", True, DIM),
            (pad + 4, H - 20))
        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    raise SystemExit(main())
