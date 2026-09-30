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
| `lidar_live.py` | the live view |
| `lidar_dump.py` | record to CSV |
| `lidar_plot.py` | draw a recorded CSV |
| `tests/test_align.py` | alignment checked against known answers |

## Tests

```bash
python3 tests/test_align.py
```

Builds a fake room with two sensors a known distance apart and checks the
alignment recovers it: within about a millimetre and a few hundredths of a
degree in a normal room, still working with 10 mm of noise or a 35-degree error
in the starting guess, and refusing (rather than guessing) when the guess is 90
degrees out or the room is a bare corridor.

## Notes

The `rplidar` Python library was written for the older A1/A2, and two things it
does trip up the C1, both handled in `lidar_io.py`:

- it toggles the serial DTR line to start a "motor" every time you iterate,
  which the C1 doesn't need
- it reads one 5-byte measurement per system call, which can't keep up with
  5000 per second

Also worth knowing: the sensor takes about 2 seconds to reach full speed, so
rates measured right after connecting look low.
