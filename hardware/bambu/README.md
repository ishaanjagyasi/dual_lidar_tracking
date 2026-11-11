# Bambu Studio presets — 0.4 nozzle, PLA

| | |
|---|---|
| `LiDAR jig @BBL A1.json` | A1 — what to use |
| `LiDAR jig + supports @BBL A1.json` | A1, with supports on, if you want them |
| `LiDAR jig @BBL X1C.json` | X1 Carbon — what to use |
| `LiDAR jig + supports @BBL X1C.json` | X1 Carbon, with supports on |

The X1C pair also covers the X1, X1E and P1S with a 0.4 nozzle. Any Generic
PLA profile will do for filament.

**Install:** Bambu Studio → *File → Import → Import Configs…* → pick the file.
Then choose it in the Process dropdown. Or drop the file straight into
`~/Library/Application Support/BambuStudio/user/<your-id>/process/` and restart.

Your filament profile needs no change. `SUNLU PLA Black Helix @A1` is already
set up and inherits `Generic PLA @BBL A1`; tweaking its cooling made no
difference to the time at all — measured, same gcode to the second.

## Print both copies on one plate

This is the whole trick. **Put two on the plate and print them together.**

The posts are thin tubes, so a single layer of one is about 140 mm of bead and
is over in a blink. Printing two means the nozzle walks off to the other part
and gives the first one that long again to set before the next layer lands. The
dwell doubles for free, and the time barely moves.

You need two anyway.

## Measured on the A1

Sliced with the actual Bambu Studio CLI against your own printer and filament
profiles, not guessed. Raised version, both copies on the plate:

| | time for the pair | how long a post layer gets to cool |
|---|---|---|
| Stock `0.28mm Extra Draft` | 7h 36m | 2.4 s |
| **`LiDAR jig` (this preset)** | **8h 17m** | **3.5 s** |
| Walls capped harder (45 mm/s) | 11h 22m | 6.2 s |

The flat version, both copies, with this preset: **4h 19m**.

Stock is 41 minutes quicker. It is also running the posts at 110–120 mm/s,
which on a 25 mm tube 200 mm tall does not leave the layer time to go solid.
This preset caps the walls at 80 mm/s to buy that back. The rest of it — 10%
infill, thin-wall detection so the 2.5 mm post wall fills properly, a 5 mm brim
because the thing is 206 mm tall — is small change by comparison.

## On the X1 Carbon

Same settings, inheriting `0.28mm Extra Draft @BBL X1C` instead. Two copies fit
the 256 mm bed comfortably — one behind the other, not side by side — and the
206 mm raised version clears the 250 mm height.

**Open it up.** The X1C is enclosed, and that is the one thing that matters
here. Posts this thin and this tall are cooling-limited, which is the whole
reason for the 80 mm/s wall cap; printing PLA in a closed, heat-soaked chamber
works against exactly that. Front door open, top glass off.

Two honest caveats:

- **The times below are the A1's.** I sliced those with Bambu Studio's own
  command line. It refuses to load any X1-family machine profile on this
  version — X1C, X1, X1E and P1S all fail the same way, while the A1 goes
  through fine — so I could not measure the X1C and will not invent a number.
  Expect it near the A1's: both cap PLA at the same 12 mm³/s, which is what
  this print runs into, so the X1C's faster motion buys less than it looks.
- The X1C schema carries one value per extruder variant, so the speeds in that
  preset are pairs rather than single values. That is deliberate; don't
  "tidy" them into one.

## About the supports

Nothing in either model needs them. The only thing printed over air is the deck
of the raised version, bridging 56 mm, and its top face comes out flat because
it is printed last.

Turning them on costs **+1h 17m** (about 14% of the print) and Bambu's
auto-arrange then can't fit two copies — it refuses with a gcode conflict,
because the supports collide. Support material would also land inside the
plinth, where the way out is the open bottom and two 26 mm windows.

The preset is there if you want it. I would not use it.

## One thing about black

The jig exists so the other sensor can see it, and the C1 works at 905 nm.
Black PLA is the worst case for that — carbon black absorbs well into the
infrared, and the posts have to read from 3.3 m away.

It may well be fine. If the posts come back faint or not at all, don't reprint:
wrap a strip of white tape or paper round each one. That costs nothing and
fixes it completely.
