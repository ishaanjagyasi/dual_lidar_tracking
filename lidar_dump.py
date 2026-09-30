# First look at what the RPLIDAR C1 sees. Prints a rotation at a time and
# saves every point to CSV.
#
#   python3 lidar_dump.py                 # 5 seconds, default port
#   python3 lidar_dump.py --seconds 20 --csv walk.csv
#
# The C1 runs at 460800 baud, spins about 10 times a second, and reports
# roughly 500 points per rotation (0.72 degrees apart).
#
# Angles: 0 degrees is straight ahead of the sensor (the marked front), and
# they increase clockwise seen from above. Distances are in millimetres,
# measured from the middle of the spinning core. 0 means "nothing there".

import argparse
import csv
import math
import time

import lidar_io

SECTORS = 24            # for the on-screen summary: 24 x 15 degrees


def sector_view(points, max_mm):
    """One line per 15-degree sector: the nearest thing in it."""
    nearest = [None] * SECTORS
    counts = [0] * SECTORS
    for angle, dist, _q in points:
        s = int(angle / (360 / SECTORS)) % SECTORS
        counts[s] += 1
        if nearest[s] is None or dist < nearest[s]:
            nearest[s] = dist

    lines = []
    for s in range(SECTORS):
        a = s * (360 // SECTORS)
        if nearest[s] is None:
            lines.append(f"  {a:3d}-{a+14:3d} deg  {counts[s]:3d} pts        (nothing)")
            continue
        bar = "#" * max(1, int(40 * (1 - min(nearest[s], max_mm) / max_mm)))
        lines.append(f"  {a:3d}-{a+14:3d} deg  {counts[s]:3d} pts  {nearest[s]/1000:5.2f} m  {bar}")
    return lines


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", default=None, help="serial port (found automatically by default)")
    p.add_argument("--baud", type=int, default=lidar_io.BAUD)
    p.add_argument("--seconds", type=float, default=5.0)
    p.add_argument("--csv", default="lidar_scan.csv")
    p.add_argument("--show", type=int, default=2, help="how many rotations to print in full")
    p.add_argument("--max-mm", type=float, default=4000.0, help="bar scale for the printout")
    args = p.parse_args()

    lidar, info, health = lidar_io.open_lidar(args.port, args.baud)
    print("info  ", info)
    print("health", health)

    fh = open(args.csv, "w", newline="")
    out = csv.writer(fh)
    out.writerow(["scan", "t_s", "angle_deg", "dist_mm", "quality"])

    t0 = time.time()
    scans = points = 0
    dists = []
    try:
        for scan in lidar_io.rotations(lidar):
            now = time.time() - t0
            scans += 1
            points += len(scan)
            good = scan
            dists.extend(d for _a, d, _q in good)

            for a, d, q in scan:
                out.writerow([scans, f"{now:.3f}", f"{a:.2f}", f"{d:.1f}", q])

            if scans <= args.show:
                print(f"\n--- rotation {scans} at {now:.2f}s: {len(scan)} points, "
                      f"{len(good)} with a reading ---")
                for line in sector_view(good, args.max_mm):
                    print(line)
            elif scans % 10 == 0:
                near = min((d for _a, d, _q in good), default=0)
                print(f"rotation {scans:4d}  t={now:5.2f}s  {len(scan):4d} points  "
                      f"nearest {near/1000:5.2f} m")

            if now >= args.seconds:
                break
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        lidar_io.close_lidar(lidar)
        fh.close()

    took = time.time() - t0
    print(f"\n--- summary ---")
    print(f"rotations      {scans} in {took:.1f}s  ({scans/took:.1f} per second)")
    print(f"points         {points}  ({points/max(scans,1):.0f} per rotation, "
          f"{points/took:.0f} per second)")
    if dists:
        dists.sort()
        print(f"distances      {dists[0]/1000:.2f} m to {dists[-1]/1000:.2f} m  "
              f"(middle value {dists[len(dists)//2]/1000:.2f} m)")
        print(f"angle step     about {360/(points/max(scans,1)):.2f} degrees")
    print(f"csv            {args.csv}")


if __name__ == "__main__":
    main()
