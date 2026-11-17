# dual_lidar_tracking

Tracks one person on a square carpet with two RPLIDAR C1 sensors, and sends
their tile to the Processing game in [gridGameWinter/](gridGameWinter/)
(copied from `myagordon/smartlab_w26`, commit 01581b5).

## Setup

- 2 x RPLIDAR C1 over USB, one at each end of the carpet's diagonal, same height.
- Print one jig per sensor from [hardware/](hardware/) (Bambu presets in
  `hardware/bambu/`). Point each jig's arrow at the other sensor.

```bash
pip install -r requirements.txt
```

## 1. Calibrate

```bash
python3 pick_pair.py
```

Two live panels, one per sensor. In each, click on the **other** sensor (wave a
hand next to it to see which blob moves). Both distances should match. `P`
polishes, `S` saves to `lidar_align.json`.

Other option: `calibrate_pair.py` (automatic).

## 2. Track and send to Processing

```bash
python3 lidar_live.py --crop --track
```

1. Keep the carpet empty, press `B`.
2. Press `O` to start sending.
3. Open `gridGameWinter/gridGameWinter.pde` in Processing, run it, click START.
4. Stand in a corner. If the wrong tile lights, press `Y` (turn grid) or `M`
   (mirror) until it's right. This is saved.

Sends `/position x y` (mm) to UDP 6800. Don't run the foot-sensor script at the
same time.

| Key | |
|---|---|
| `B` | learn the empty carpet |
| `T` | follow a person |
| `O` | send to Processing on / off |
| `Y` / `M` | turn / mirror the grid |
| `V` | crop on / off: keeps the mat + 2 m on every side (`--margin` to change) |
| `K` | auto-align by matching walls |
| `S` / `L` | save / reload calibration |
| `ESC` | quit |

## Files

| | |
|---|---|
| `lidar_live.py` | live view, tracking, sending |
| `pick_pair.py` | calibrate by clicking |
| `calibrate_pair.py` | automatic calibration (also used by `pick_pair.py`) |
| `tracker.py` | finding legs and following a person |
| `carpet_grid.py` | carpet to game grid |
| `area.py` | carpet crop |
| `align.py` | wall matching (ICP) |
| `lidar_io.py` | reading the sensors |
| `gridGameWinter/` | the Processing game |
| `hardware/` | 3D-printable jig |
| `vendor/` | SLAMTEC docs and SDK |
