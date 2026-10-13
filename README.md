# dual_lidar_tracking

Reading two SLAMTEC RPLIDAR C1 scanners at once, drawing them live, and lining
them up with each other automatically.

The eventual goal is tracking feet on a floor grid for an interactive game, by
scanning a thin slice of air just above the floor. What's here now is the
groundwork: reliable reading, a live view, and calibration between the two
sensors. **Foot detection is not built yet.**

## Hardware

- 2 x RPLIDAR C1, over USB (they appear as `/dev/cu.usbserial-*` on macOS)
- 460800 baud, ~10 rotations/second, ~450 points per rotation (~0.8 deg apart)
- Blind zone 0.05 m, useful range 12 m

Two sensors are used because one foot can hide another. Put them at opposite
corners, at shoe height, 1-2 cm apart in height so their lasers don't confuse
each other.

## Install

```bash
pip install -r requirements.txt
```

## Live view

```bash
python3 lidar_live.py              # every lidar it can find
python3 lidar_live.py --port /dev/cu.usbserial-2130
```

Each sensor draws in its own colour. They start stacked on top of each other,
because a sensor only knows distances in its own coordinates.

| Key | |
|---|---|
| `TAB` | pick a sensor to move |
| arrows | move it |
| `<` `>` | turn it |
| `K` | **line it up automatically** |
| `V` | carpet crop: off / wedge / wedge + square |
| `B` | learn the empty carpet (stay off it) |
| `T` | follow a person |
| `S` / `L` | save / reload alignment |
| `0` | reset the picked sensor |
| `C` | save what's on screen as a CSV |
| `P` / `G` | trails / 500 mm grid |
| drag, wheel, `R` | pan, zoom, reset view |
| `ESC` | quit |

Alignment is stored in `lidar_align.json`, keyed by each sensor's serial
number, so it survives the ports swapping around.

## Lining the sensors up

Nudge one roughly into place by eye, clear people out of the area, then press
`K`. It matches the shapes both sensors can see (ICP - iterative closest
point), and reports how well it did:

```
B: aligned: 7 mm off the walls, 310 points matched   (S to keep it)
```

It refuses rather than guessing when it can't be trusted:

- **poor match** - the starting guess was too far off
- **the shape here is too plain** - a bare corridor looks the same wherever you
  slide along it, so it pokes its own answer to check whether the room shape
  really pins it down
- **not enough points yet** - let the sensors spin a moment

Each point is matched to the *wall* its nearest neighbour sits on, not to that
point itself. The two sensors never sample the same spots on a wall, so
point-to-point matching drags the answer along the wall by a few centimetres.

## Cropping to the carpet

The sensors sit at opposite ends of the carpet's diagonal, so `V` cuts away
everything that isn't on it. Two filters, both worked out from where the
sensors are, so nothing has to be measured and the carpet can be any size:

- **the wedge** - each sensor only looks in a cone facing the other one, 145
  degrees by default (`--fov`). A square corner spans exactly 90 degrees, so
  anything above that is margin for catching a foot stepping off the edge.
- **the square** - two opposite corners fix a square completely, so points
  outside it are dropped. `--margin` (0.2 m by default) keeps a little of the
  floor just outside the edge.

Dropped points are still drawn, very dim, so you can see what is being cut.

This assumes the carpet is square. A rectangle isn't fixed by its diagonal
alone and would need its side length measured too.

## Following a person

`B` with the carpet empty, then `T`. It reports the point midway between your
two legs, in metres from sensor A.

It works whether the sensors are low enough to see shoes or high enough to see
shins - the logic only cares that there are one or two blobs, not what part of
a leg they are.

1. **background** - with the carpet empty, it remembers how far the nearest
   static thing is at every angle. Anything nearer than that later is a person.
2. **blobs** - the leftover points are grouped. Each blob is a leg.
3. **midpoint** - two blobs give the point between them. One wide blob is both
   legs together. One narrow blob is a single leg, and the midpoint is placed
   using the offset last measured between that leg and the middle.

**A leg in mid-stride lifts clear of the scan slice and disappears, so seeing
only one is normal while walking.** In a simulated lap that was the case on
182 of 238 readings, which is why the one-leg rule matters more than it sounds.

When nothing is visible at all it keeps moving at the last speed for 0.3 s,
then stands still for a second, then gives up and says so. It never keeps
publishing a position as though it were fresh: the state and the age of the
last real sighting are always on screen.

## Recording and plotting

```bash
python3 lidar_dump.py --seconds 10 --csv walk.csv    # record, with a text summary
python3 lidar_plot.py walk.csv                       # top-down picture
```

## Files

| | |
|---|---|
| `lidar_io.py` | opening, reading and closing a sensor |
| `align.py` | automatic alignment between sensors |
| `area.py` | the wedge and carpet-square filters |
| `tracker.py` | background, blobs, and following a person |
| `lidar_live.py` | the live view |
| `lidar_dump.py` | record to CSV |
| `lidar_plot.py` | draw a recorded CSV |
| `tests/test_align.py` | alignment checked against known answers |
| `tests/test_area.py` | carpet filter checked against known geometry |
| `tests/test_tracker.py` | tracking checked against a made-up walk |

## Tests

```bash
python3 tests/test_align.py
python3 tests/test_area.py
python3 tests/test_tracker.py
```

Builds a fake room with two sensors a known distance apart and checks the
alignment recovers it: within about a millimetre and a few hundredths of a
degree in a normal room, still working with 10 mm of noise or a 35-degree error
in the starting guess, and refusing (rather than guessing) when the guess is 90
degrees out or the room is a bare corridor.

`test_area.py` checks the carpet square comes out right for any size at any
angle, that the 90-degree fact holds, and that a point just off the edge is
dropped unless the margin covers it.

`test_tracker.py` walks an imaginary person past imaginary sensors: both legs
visible, one leg vanishing mid-stride, feet together, a total dropout, a bag
left on the carpet, and an impossible jump. Running the whole app against two
fake sensors with someone walking a lap, the midpoint stayed within 4 cm
(median; 10 cm at worst) of where that person actually was, never gave up while
they were walking, and reported "lost" once they left.

## Notes

The `rplidar` Python library was written for the older A1/A2, and two things it
does trip up the C1, both handled in `lidar_io.py`:

- it toggles the serial DTR line to start a "motor" every time you iterate,
  which the C1 doesn't need
- it reads one 5-byte measurement per system call, which can't keep up with
  5000 per second

Also worth knowing: the sensor takes about 2 seconds to reach full speed, so
rates measured right after connecting look low.

## Vendor material

`vendor/` holds SLAMTEC's own files, unmodified, so the protocol details stay
next to the code that relies on them:

- `vendor/docs/` - C1 datasheet and kit user manual, plus the S-series protocol
  and SDK manuals. The C1 speaks the same protocols.
- `vendor/sdk/` - the official `rplidar_sdk` (C++). Not used at runtime, but it
  is the reference for anything the Python library doesn't cover, such as the
  high-speed "dense capsule" scan mode.

SLAMTEC's SDK is BSD 2-clause; its `LICENSE` is kept with it. Not included: the
RoboStudio app (Windows only), the SDK zip (same as the extracted folder), and
the C1 3D model, all available from SLAMTEC.
