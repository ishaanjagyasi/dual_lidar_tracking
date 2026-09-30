# Live view of one or more RPLIDARs, in pygame.
#
#   python3 lidar_live.py                          # every lidar it can find
#   python3 lidar_live.py --port /dev/cu.usbserial-2130
#
# Each sensor draws in its own colour. They start stacked on top of each
# other, because a sensor only knows distances in its own coordinates. Line
# them up by eye: pick one with TAB, then move and turn it with the arrow keys
# until the walls from both sensors sit on top of each other. Press S to save,
# and it comes back next time (remembered per sensor serial number).
#
# K lines the picked sensor up with sensor A automatically, by matching the
# shapes both of them see (see align.py). Nudge it roughly into place first,
# keep people out of the area, and press K.
#
# Keys:  TAB pick a sensor   arrows move it   < > turn it   0 reset it
#        K line it up automatically
#        S save alignment    L reload it
#        drag / wheel to pan and zoom   R reset view
#        P trails   G 500mm grid   C save a CSV of what's on screen   ESC quit
#        hold SHIFT for bigger steps

import argparse
import csv
import json
import math
import os
import threading
import time
from collections import deque

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

import align
import lidar_io

HERE = os.path.dirname(os.path.abspath(__file__))
ALIGN_FILE = os.path.join(HERE, "lidar_align.json")

WIDTH, HEIGHT = 1100, 850
BG = (16, 18, 24)
RING = (52, 58, 70)
GRID = (40, 60, 80)
TEXT = (225, 230, 240)
DIM = (130, 140, 155)
WARN = (245, 180, 70)
OK = (80, 210, 130)
PICKED = (255, 255, 255)

# one colour per sensor: points, and a dimmer version for trails
COLOURS = [
    ((90, 200, 255), (35, 80, 105)),
    ((255, 165, 70), (105, 68, 28)),
    ((150, 245, 140), (60, 100, 55)),
    ((235, 130, 235), (95, 55, 95)),
]
HISTORY = 12


class Sensor(threading.Thread):
    """Reads one lidar on its own thread and holds its newest rotation."""

    def __init__(self, port, baud, name, colours):
        super().__init__(daemon=True)
        self.port, self.baud, self.name = port, baud, name
        self.colour, self.trail_colour = colours
        self.lock = threading.Lock()
        self.scan = []
        self.history = deque(maxlen=HISTORY)
        self.info = None
        self.serial = None
        self.error = None
        self.rotations = 0
        self.rate = 0.0
        self.offset = [0.0, 0.0, 0.0]     # metres right, metres up, degrees
        self.stop = threading.Event()

    def run(self):
        lidar = None
        try:
            lidar, self.info, _health = lidar_io.open_lidar(self.port, self.baud, quiet=True)
            self.serial = self.info.get("serialnumber")
            t0, n0 = time.time(), 0
            for pts in lidar_io.rotations(lidar):
                if self.stop.is_set():
                    break
                with self.lock:
                    if self.scan:
                        self.history.append(self.scan)
                    self.scan = pts
                    self.rotations += 1
                now = time.time()
                if now - t0 >= 1.0:
                    self.rate = (self.rotations - n0) / (now - t0)
                    t0, n0 = now, self.rotations
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
        finally:
            if lidar is not None:
                lidar_io.close_lidar(lidar)

    def snapshot(self):
        with self.lock:
            return list(self.scan), [list(h) for h in self.history]

    def to_world(self, angle_deg, dist_mm):
        """This sensor's own reading, placed on the shared map, in metres."""
        a = math.radians(angle_deg + self.offset[2])
        d = dist_mm / 1000.0
        return self.offset[0] + d * math.sin(a), self.offset[1] + d * math.cos(a)


class View:
    def __init__(self):
        self.scale = 110.0      # pixels per metre
        self.pan = [0.0, 0.0]   # metres

    def to_screen(self, x, y):
        return (int(WIDTH / 2 + (x - self.pan[0]) * self.scale),
                int(HEIGHT / 2 - (y - self.pan[1]) * self.scale))


def load_alignment(sensors):
    if not os.path.exists(ALIGN_FILE):
        return "no saved alignment"
    try:
        saved = json.load(open(ALIGN_FILE))
    except Exception as exc:
        return f"could not read alignment: {exc}"
    found = 0
    for s in sensors:
        if s.serial and s.serial in saved:
            v = saved[s.serial]
            s.offset = [float(v["x"]), float(v["y"]), float(v["rot"])]
            found += 1
    return f"loaded alignment for {found} sensor(s)"


def save_alignment(sensors):
    saved = {}
    if os.path.exists(ALIGN_FILE):
        try:
            saved = json.load(open(ALIGN_FILE))
        except Exception:
            saved = {}
    for s in sensors:
        if s.serial:
            saved[s.serial] = {"x": s.offset[0], "y": s.offset[1], "rot": s.offset[2],
                               "port_last_seen": s.port, "name": s.name}
    with open(ALIGN_FILE, "w") as fh:
        json.dump(saved, fh, indent=2)
    return f"saved to {os.path.basename(ALIGN_FILE)}"


def save_csv(sensors):
    name = os.path.join(HERE, time.strftime("scan_%Y%m%d_%H%M%S.csv"))
    with open(name, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["sensor", "serial", "angle_deg", "dist_mm", "quality", "x_m", "y_m"])
        for s in sensors:
            scan, _h = s.snapshot()
            for a, d, q in scan:
                x, y = s.to_world(a, d)
                w.writerow([s.name, s.serial or "", f"{a:.2f}", f"{d:.1f}", q,
                            f"{x:.4f}", f"{y:.4f}"])
    return f"saved {os.path.basename(name)}"


def calibrate(sensors, picked, note_box):
    """Match the picked sensor's shapes onto the other sensors' (runs off the
    render loop so the view keeps moving)."""
    target_sensors = [s for n, s in enumerate(sensors) if n != picked and s.rotations]
    me = sensors[picked]
    if not target_sensors:
        note_box[0] = "nothing to line up against - only one sensor is running"
        return
    if not me.rotations:
        note_box[0] = f"sensor {me.name} has no data yet"
        return

    # use several rotations from each, for a fuller picture of the room
    mine = []
    for pts in list(me.history) + [me.scan]:
        mine.extend(pts)
    theirs = []
    for s in target_sensors:
        for pts in list(s.history) + [s.scan]:
            theirs.extend(s.to_world(a, d) for a, d, _q in pts)

    note_box[0] = f"matching sensor {me.name}..."
    pose, message = align.calibrate(mine, theirs, tuple(me.offset))
    if pose is not None:
        me.offset = list(pose)
        message += "   (S to keep it)"
    note_box[0] = f"{me.name}: {message}"


def draw_rings(surf, view, font):
    centre = view.to_screen(0, 0)
    for r in range(1, 13):
        px = int(r * view.scale)
        if px < 25:
            continue
        if px > 2 * (WIDTH + HEIGHT):
            break
        pygame.draw.circle(surf, RING, centre, px, 1)
        surf.blit(font.render(f"{r} m", True, RING), (centre[0] + 4, centre[1] - px - 16))


def draw_grid(surf, view, tile_m):
    half_w = (WIDTH / 2) / view.scale
    half_h = (HEIGHT / 2) / view.scale
    i = math.floor((view.pan[0] - half_w) / tile_m)
    while i * tile_m <= view.pan[0] + half_w:
        x, _ = view.to_screen(i * tile_m, 0)
        pygame.draw.line(surf, GRID, (x, 0), (x, HEIGHT), 1)
        i += 1
    j = math.floor((view.pan[1] - half_h) / tile_m)
    while j * tile_m <= view.pan[1] + half_h:
        _, y = view.to_screen(0, j * tile_m)
        pygame.draw.line(surf, GRID, (0, y), (WIDTH, y), 1)
        j += 1


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", action="append", help="use this port (repeat for more sensors)")
    p.add_argument("--baud", type=int, default=lidar_io.BAUD)
    p.add_argument("--persist", action="store_true", help="start with trails on")
    p.add_argument("--tile", type=float, default=0.5, help="grid square size in metres")
    p.add_argument("--seconds", type=float, help="auto-quit after N seconds (testing)")
    p.add_argument("--shot", help="save a screenshot on quit (testing)")
    args = p.parse_args()

    ports = args.port or lidar_io.find_ports()
    if not ports:
        print("no lidar found - is it plugged in?")
        return
    sensors = [Sensor(port, args.baud, chr(ord("A") + n), COLOURS[n % len(COLOURS)])
               for n, port in enumerate(ports)]
    for s in sensors:
        print(f"sensor {s.name}: {s.port}")
        s.start()

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("RPLIDAR — live")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Menlo, Monaco, monospace", 15)
    big = pygame.font.SysFont("Menlo, Monaco, monospace", 18, bold=True)

    view = View()
    picked = 0 if len(sensors) == 1 else 1     # the one the arrows move
    persist = args.persist
    show_grid = False
    note_box = [""]          # a list so the calibrate thread can write to it
    loaded = False
    dragging = False
    started = time.time()

    running = True
    while running:
        shift = pygame.key.get_mods() & pygame.KMOD_SHIFT
        move = 0.10 if shift else 0.01         # metres per key press
        turn = 5.0 if shift else 0.5           # degrees per key press

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                dragging = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragging = False
            elif event.type == pygame.MOUSEMOTION and dragging:
                view.pan[0] -= event.rel[0] / view.scale
                view.pan[1] += event.rel[1] / view.scale
            elif event.type == pygame.MOUSEWHEEL:
                view.scale = max(5.0, min(2000.0, view.scale * (1.1 ** event.y)))
            elif event.type == pygame.KEYDOWN:
                k = event.key
                if k in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif k == pygame.K_TAB:
                    picked = (picked + 1) % len(sensors)
                elif k == pygame.K_LEFT:
                    sensors[picked].offset[0] -= move
                elif k == pygame.K_RIGHT:
                    sensors[picked].offset[0] += move
                elif k == pygame.K_UP:
                    sensors[picked].offset[1] += move
                elif k == pygame.K_DOWN:
                    sensors[picked].offset[1] -= move
                elif k == pygame.K_COMMA:
                    sensors[picked].offset[2] -= turn
                elif k == pygame.K_PERIOD:
                    sensors[picked].offset[2] += turn
                elif k == pygame.K_0:
                    sensors[picked].offset = [0.0, 0.0, 0.0]
                elif k == pygame.K_k:
                    threading.Thread(target=calibrate,
                                     args=(sensors, picked, note_box),
                                     daemon=True).start()
                elif k == pygame.K_s:
                    note_box[0] = save_alignment(sensors)
                elif k == pygame.K_l:
                    note_box[0] = load_alignment(sensors)
                elif k == pygame.K_c:
                    note_box[0] = save_csv(sensors)
                elif k == pygame.K_p:
                    persist = not persist
                elif k == pygame.K_g:
                    show_grid = not show_grid
                elif k == pygame.K_r:
                    view.scale, view.pan = 110.0, [0.0, 0.0]

        # once the serial numbers are known, bring back any saved alignment
        if not loaded and all(s.serial or s.error for s in sensors):
            note_box[0] = load_alignment(sensors)
            loaded = True

        screen.fill(BG)
        if show_grid:
            draw_grid(screen, view, args.tile)
        draw_rings(screen, view, font)

        for s in sensors:
            scan, history = s.snapshot()
            if persist:
                for old in history:
                    for a, d, _q in old:
                        x, y = s.to_world(a, d)
                        px, py = view.to_screen(x, y)
                        if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                            screen.set_at((px, py), s.trail_colour)
            for a, d, q in scan:
                f = 0.35 + 0.65 * min(q, 50) / 50.0
                colour = tuple(int(c * f) for c in s.colour)
                pygame.draw.circle(screen, colour, view.to_screen(*s.to_world(a, d)), 2)

            # the sensor itself, and which way its 0 degrees points
            centre = view.to_screen(s.offset[0], s.offset[1])
            pygame.draw.circle(screen, s.colour, centre, 7)
            if s is sensors[picked]:
                pygame.draw.circle(screen, PICKED, centre, 12, 2)
            a = math.radians(s.offset[2])
            tip = (centre[0] + math.sin(a) * 34, centre[1] - math.cos(a) * 34)
            pygame.draw.line(screen, s.colour, centre, tip, 2)
            screen.blit(font.render(s.name, True, s.colour), (centre[0] + 10, centre[1] + 6))

        # ---- panel
        lines = []
        for n, s in enumerate(sensors):
            scan, _h = s.snapshot()
            mark = ">" if n == picked else " "
            if s.error:
                lines.append((f"{mark} {s.name}  ERROR {s.error[:38]}", WARN))
                continue
            serial = (s.serial or "")[:8]
            lines.append((f"{mark} {s.name}  {os.path.basename(s.port):18s} {serial}", s.colour))
            lines.append((f"    {len(scan):4d} points   {s.rate:4.1f} rot/s   "
                          f"x {s.offset[0]:+.2f} y {s.offset[1]:+.2f} turn {s.offset[2]:+6.1f}", DIM))

        live = [s for s in sensors if s.rotations and not s.error]
        if not live:
            head, colour = "waiting for the sensors...", WARN
        else:
            head, colour = f"live   {len(live)} sensor(s)", OK
        lines.append(("", DIM))
        lines.append((note_box[0] or
                      "TAB picks a sensor, arrows move it roughly, K lines it up, S saves", DIM))

        panel = pygame.Surface((640, 24 * len(lines) + 58), pygame.SRCALPHA)
        panel.fill((10, 12, 16, 215))
        screen.blit(panel, (12, 12))
        screen.blit(big.render(head, True, colour), (24, 24))
        for n, (text, c) in enumerate(lines):
            screen.blit(font.render(text[:74], True, c), (24, 56 + n * 24))

        help_text = ("TAB pick  arrows move  < > turn  K auto-align  0 reset  S save  "
                     "L load  C csv  P trails  G grid  R view  ESC quit")
        hint = font.render(help_text, True, DIM)
        screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, HEIGHT - 26))

        pygame.display.flip()
        clock.tick(60)

        if args.seconds and time.time() - started > args.seconds:
            running = False

    if args.shot:
        pygame.image.save(screen, args.shot)
        print("screenshot", args.shot)
    # Let each reader stop and close its own port before we leave, otherwise
    # closing a port out from under a blocked read can hang for a while.
    for s in sensors:
        s.stop.set()
    for s in sensors:
        s.join(timeout=2.0)
    pygame.quit()
    for s in sensors:
        print(f"{s.name}: {s.rotations} rotations, {s.rate:.1f}/s, serial {s.serial}"
              + (f", ERROR {s.error}" if s.error else ""))


if __name__ == "__main__":
    main()
