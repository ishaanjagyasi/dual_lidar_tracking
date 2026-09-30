# Opening and reading the RPLIDAR C1, reliably.
#
# The rplidar library was written for the older A1/A2. Two things it does trip
# up the C1:
#   - it toggles the serial DTR line to start the "motor" every time you begin
#     iterating, which the C1 doesn't need and which can upset the link
#   - it asks the sensor for its health right after that, and if any stray
#     bytes are still in the buffer the reply is misread ("Descriptor length
#     mismatch")
# So: stop, flush, start the motor once, flush again, and retry a few times.

import glob
import time

from rplidar import RPLidar

BAUD = 460800          # the C1 runs at this; the A1's 115200 will not work
SCAN_TYPE = "normal"
READ_TIMEOUT = 0.5     # short, so a reader thread notices a stop quickly


def find_ports():
    """Every USB serial port that could be a lidar, in a stable order.

    On macOS the same device can appear twice, as cu.usbserial-XXXX and as
    cu.SLAB_USBtoUART, so the SLAB names are only used if nothing else shows up.
    """
    found = sorted(glob.glob("/dev/cu.usbserial*")) + sorted(glob.glob("/dev/ttyUSB*"))
    if not found:
        found = sorted(glob.glob("/dev/cu.SLAB_USBtoUART*"))
    return found


def find_port(preferred=None):
    """Pick one serial port: the given one, else the first that looks right."""
    if preferred:
        return preferred
    found = find_ports()
    if not found:
        raise RuntimeError("no USB serial port found - is the lidar plugged in?")
    return found[0]


def open_lidar(port=None, baud=BAUD, attempts=5, quiet=False):
    """Returns (lidar, info, health), already scanning. Retries on desync."""
    port = find_port(port)
    last = None
    for n in range(1, attempts + 1):
        lidar = None
        try:
            lidar = RPLidar(port, baudrate=baud, timeout=READ_TIMEOUT)
            # It may still be streaming from a previous run.
            lidar.stop()
            time.sleep(0.3)
            lidar.clean_input()

            lidar.start_motor()
            time.sleep(0.3)
            lidar.clean_input()

            info = lidar.get_info()
            health = lidar.get_health()
            lidar.start(SCAN_TYPE)

            # The library calls start_motor() again every time you iterate,
            # which toggles DTR mid-stream. Once is enough.
            lidar.start_motor = lambda: None
            return lidar, info, health
        except Exception as exc:
            last = exc
            if not quiet:
                print(f"  open attempt {n}/{attempts}: {type(exc).__name__}: {exc}")
            if lidar is not None:
                try:
                    lidar.stop()
                    lidar.disconnect()
                except Exception:
                    pass
            time.sleep(0.6)
    raise RuntimeError(f"could not start the lidar on {port}: {last}")


def close_lidar(lidar):
    """Close from the same thread that was reading. The C1's motor stops with
    the scan, so there is no separate motor command to send."""
    try:
        lidar.stop()
        lidar.disconnect()
    except Exception:
        pass


def rotations(lidar, min_len=5, keep_blanks=False):
    """Yields one rotation at a time as a list of (angle_deg, dist_mm, quality).

    Reads the serial port in bulk and unpacks the 5-byte measurements here.
    The library reads one measurement per system call, which cannot keep up
    with 5000 per second, so it silently drops data.

    Each measurement is:
      byte 0  quality in the top 6 bits; bit 0 marks a new rotation, and bit 1
              is its opposite, which is how a valid packet is recognised
      byte 1  bit 0 is always 1; the rest are the low bits of the angle
      byte 2  the high bits of the angle (angle is in 64ths of a degree)
      byte 3-4  distance in quarters of a millimetre, low byte first
    """
    ser = lidar._serial
    buf = bytearray()
    scan = []
    while True:
        chunk = ser.read(max(1, ser.in_waiting))
        if not chunk:
            continue
        buf.extend(chunk)

        i = 0
        while len(buf) - i >= 5:
            b0, b1 = buf[i], buf[i + 1]
            if (b0 & 1) == ((b0 >> 1) & 1) or not (b1 & 1):
                i += 1            # not a packet boundary, shuffle along
                continue
            new_rotation = b0 & 1
            quality = b0 >> 2
            angle = ((buf[i + 2] << 7) | (b1 >> 1)) / 64.0
            dist = ((buf[i + 4] << 8) | buf[i + 3]) / 4.0
            i += 5

            if new_rotation and scan:
                if len(scan) >= min_len:
                    yield scan
                scan = []
            if dist > 0 or keep_blanks:
                scan.append((angle, dist, quality))
        del buf[:i]
