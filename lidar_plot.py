# Draws a lidar_dump.py CSV as a top-down picture of what the sensor sees.
#
#   python3 lidar_plot.py lidar_scan.csv --save scan.png
#
# The sensor sits at the middle. 0 degrees (its marked front) points up, and
# angles increase clockwise, matching the C1's own coordinate system.

import argparse
import csv
import math

import matplotlib.pyplot as plt


def load(path, scans=None):
    pts = []
    with open(path) as fh:
        for r in csv.DictReader(fh):
            d = float(r["dist_mm"])
            if d <= 0:
                continue
            if scans and int(r["scan"]) not in scans:
                continue
            a = math.radians(float(r["angle_deg"]))
            # 0 deg up, clockwise
            pts.append((d * math.sin(a) / 1000, d * math.cos(a) / 1000, int(r["scan"])))
    return pts


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv")
    p.add_argument("--save")
    p.add_argument("--last", type=int, help="only the last N rotations")
    p.add_argument("--range", type=float, default=0, help="axis limit in metres (0 = fit)")
    p.add_argument("--no-show", action="store_true")
    args = p.parse_args()

    pts = load(args.csv)
    if not pts:
        print("no points with a reading in that file")
        return
    if args.last:
        keep = set(sorted({s for _x, _y, s in pts})[-args.last:])
        pts = [q for q in pts if q[2] in keep]

    xs = [q[0] for q in pts]
    ys = [q[1] for q in pts]

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(xs, ys, s=3, c="tab:blue", alpha=0.5, label=f"{len(pts)} points")
    ax.plot(0, 0, "ro", ms=10, label="sensor")
    ax.plot([0, 0], [0, max(0.5, max(ys, default=1) * 0.15)], "r-", lw=2)
    ax.annotate("0 deg (front)", (0, max(0.5, max(ys, default=1) * 0.15)),
                color="r", ha="center", va="bottom")

    lim = args.range or max(1.0, max(max(map(abs, xs)), max(map(abs, ys))) * 1.1)
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
    for r in range(1, int(lim) + 1):
        ax.add_artist(plt.Circle((0, 0), r, fill=False, color="gray", alpha=0.3, lw=0.6))
        ax.annotate(f"{r}m", (0.02, r), color="gray", fontsize=8)
    ax.set_aspect("equal"); ax.grid(alpha=0.2)
    ax.set_xlabel("metres"); ax.set_ylabel("metres")
    ax.set_title(args.csv)
    ax.legend(loc="lower right", fontsize=9)

    if args.save:
        fig.savefig(args.save, dpi=140, bbox_inches="tight")
        print("saved", args.save)
    if not args.no_show:
        plt.show()


if __name__ == "__main__":
    main()
