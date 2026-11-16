# dual_lidar_tracking

Tracks one person on a square carpet with two RPLIDAR C1 sensors, and sends
their tile to the Processing game (`smartlab_w26/gridGameWinter`).

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

Other options: `calibrate_pair.py` (automatic), `check_pair.py` (why it fails).

## 2. Track and send to Processing

```bash
python3 lidar_live.py --crop --track
```

1. Keep the carpet empty, press `B`.
2. Press `O` to start sending.
3. In Processing, click START.
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
| `V` | carpet crop mode |
| `K` | auto-align by matching walls |
| `S` / `L` | save / reload calibration |
| `ESC` | quit |

## Files

| | |
|---|---|
| `lidar_live.py` | live view, tracking, sending |
| `pick_pair.py` | calibrate by clicking |
| `calibrate_pair.py` / `check_pair.py` | automatic calibration / diagnosis |
| `tracker.py` | finding legs and following a person |
| `carpet_grid.py` | carpet to game grid |
| `area.py` | carpet crop |
| `align.py` | wall matching (ICP) |
| `lidar_io.py` | reading the sensors |
| `lidar_dump.py` / `lidar_plot.py` | record / plot a CSV |
| `hardware/` | 3D-printable jig |
| `tests/` | run each with `python3 tests/<file>.py` |
| `vendor/` | SLAMTEC docs and SDK |
