// Calibration target for the RPLIDAR C1 - a drop-over jig with two tall posts.
//
// WHY IT LOOKS LIKE THIS
//
// calibrate_pair.py works by letting the two sensors see each other. For that
// each one needs something the other can measure, and it has to sit exactly on
// the sensor's spin axis or the answer is off by however far it misses.
//
// Nothing can sit on the axis: that is where the sensor is. So instead two
// posts straddle it, one each side, exactly opposite. The midpoint between
// them IS the axis, whichever way round the jig is turned, and a lidar sees
// both posts from anywhere in the room. The code looks for a pair of blobs
// 2 * post_offset apart and takes the middle.
//
// Three numbers out of SLAMTEC's own drawing and STEP model set the rest:
//
// 55.6 mm square, 10 mm corner radius
//     The footprint, with the corner arcs centred at (+/-17.8, +/-17.8). Four
//     corner cradles grip those arcs, which leaves all four sides open, so the
//     cable can leave in any direction and nothing has to be threaded through.
//
// laser at 29.8 mm, total height 41.3 mm
//     The laser window is 11.5 mm BELOW the top of the case. Anything resting
//     on top of the sensor is above the beam and invisible, which is why this
//     is a jig around it rather than a hat on it.
//
// scan field flatness 0 to 1.5 degrees
//     The scan plane is not promised to be level. At 1.5 degrees it has
//     drifted 89 mm up or down by the time it has crossed 3.4 m of carpet, so
//     a short marker at 29.8 mm could be missed entirely. Hence posts 120 mm
//     tall: they cover 29.8 mm give or take 90.
//
// The posts stick out sideways, at right angles to the arrow. Aim the arrow at
// the other sensor and they sit at +/-90 degrees - outside the 145 degree
// wedge the sensors actually watch, so they block nothing that matters. A
// square carpet corner is only 90 degrees wide, so there is room to spare.
//
// Print two, one per sensor. Light grey or white, matte: 905 nm infrared comes
// back better off a pale surface. No supports - every overhang is a cone.
// Fit the jig, run the calibration, lift it off again; it is not meant to live
// on the carpet.

/* [Sensor - from SLAMTEC's drawing, do not change] */
sensor_half  = 27.8;   // half of the 55.6 mm square footprint
corner_r     = 10.0;   // corner fillet radius
screw_pitch  = 21.5;   // the 43 x 43 mm M2.5 pattern, half of it

/* [Fit] */
fit          = 0.5;    // clearance around the sensor, per side
floor_t      = 3.0;    // plate under the sensor
wall_t       = 2.5;    // cradle wall
wall_h       = 8.0;    // how far the cradle comes up the case
side_gap     = 30.0;   // opening in each side, for the cable

/* [Riser - 0 for the flat version] */
riser_h      = 0;      // how far off the floor to lift the sensor
riser_wall   = 3.0;
riser_gap    = 26.0;   // windows front and back: cable out, screwdriver in

/* [Posts] */
post_offset  = 80.0;   // post centre to spin axis
post_d       = 25.0;   // thick enough to catch a laser hit across the room
post_wall    = 2.5;
skirt_h      = 6.0;
skirt_flare  = 8.0;

/* [Arms and arrow] */
arm_w        = 18.0;
rib_w        = 3.0;
rib_h        = 12.0;
rib_gap      = 12.0;   // twin ribs, straddling the cable's way out
tab_len      = 21.0;
tab_w        = 22.0;
arrow_rise   = 1.5;

/* [Optional screws] */
screws       = true;   // 4 x M2.5 clearance holes into the sensor's own threads
screw_clear  = 2.8;
screw_cbore  = 5.6;
screw_cdepth = 1.8;

/* [How tall the posts have to be] */
laser_z      = 29.8;   // where the beam leaves the sensor, above its own base
tilt_deg     = 1.5;    // SLAMTEC's scan field flatness, worst case
reach_m      = 3.4;    // how far apart the sensors are, in metres

$fn = 72;

// The posts have to cross the other sensor's beam, and that beam is only
// promised level to within tilt_deg. Over reach_m it can have drifted this far
// up or down, so the post has to be tall enough to still be in its way.
drift    = reach_m * 1000 * tan(tilt_deg);
deck_z   = riser_h;              // underside of the plate the sensor sits on
base_z   = riser_h + floor_t;    // the sensor's own base, i.e. its zero
post_top = base_z + laser_z + drift + 4;
post_h   = post_top - floor_t;

// With the sensor on the floor a downward tilt is self-limiting - the beam
// hits the carpet after about a metre and never arrives - so only the upward
// case sets the height. Lift the sensor and the downward case starts to
// matter too, but the post already runs all the way to the ground, so it is
// covered either way.

// The footprint as SLAMTEC draws it: a square of half-width 17.8 grown by a
// 10 mm radius. Both numbers come straight out of the STEP model.
module footprint(extra = 0) {
    offset(r = corner_r + extra)
        square([2 * (sensor_half - corner_r), 2 * (sensor_half - corner_r)],
               center = true);
}

outer_half = sensor_half + fit + wall_t;

module plate() {
    // On the floor this is a solid plate. On a plinth it becomes a ring, or
    // it would seal the bottom of the tube and put the four screw heads
    // somewhere no screwdriver can reach.
    linear_extrude(floor_t)
        if (riser_h > 0)
            difference() {
                footprint(fit + wall_t);
                footprint(fit + wall_t - riser_wall);
            }
        else
            footprint(fit + wall_t);
}

module riser() if (riser_h > 0) {
    // A plinth with a window front and back, running the full height from the
    // base ring right up to the underside of the deck. The windows are how the
    // cable gets out and how a screwdriver gets in; the bottom is open too, so
    // the four screws can be reached from directly below as well. What is left
    // carries the load: a continuous ring at the floor, the four corners all
    // the way up, and the deck across the top.
    difference() {
        translate([0, 0, floor_t])
            linear_extrude(riser_h - floor_t)
                difference() {
                    footprint(fit + wall_t);
                    footprint(fit + wall_t - riser_wall);
                }
        for (a = [0, 180])
            rotate([0, 0, a])
                translate([0, outer_half, (riser_h + floor_t) / 2])
                    cube([riser_gap, 4 * riser_wall, riser_h + 2], center = true);
    }

    // the deck the sensor stands on
    translate([0, 0, riser_h]) linear_extrude(floor_t) footprint(fit + wall_t);
}


module cradle() {
    // A full ring, then most of each side cut away. What survives is four
    // corner cradles sitting on the arcs, which is where the case is roundest
    // and so where it locates best.
    difference() {
        translate([0, 0, deck_z + floor_t])
            linear_extrude(wall_h)
                difference() {
                    footprint(fit + wall_t);
                    footprint(fit);
                }
        for (a = [0, 90, 180, 270])
            rotate([0, 0, a])
                translate([0, outer_half, deck_z + floor_t - 1])
                    cube([side_gap, 4 * wall_t, wall_h + 2], center = true);
    }
}

module arm(sign) {
    // Flush with the plate, so nothing stands proud under the sensor, with a
    // rib added once it is clear of the case.
    translate([sign * post_offset / 2, 0, floor_t / 2])
        cube([post_offset, arm_w, floor_t], center = true);
    // Two ribs rather than one down the middle: the UART cable leaves through
    // the middle of a face, and a single central rib would sit right in
    // front of it. The gap between these lets it out.
    for (y = [-rib_gap / 2, rib_gap / 2])
        translate([sign * (outer_half + (post_offset - outer_half) / 2), y,
                   floor_t + rib_h / 2 - 0.01])
            cube([post_offset - outer_half, rib_w, rib_h], center = true);
}

module post(sign) {
    translate([sign * post_offset, 0, floor_t]) {
        difference() {
            union() {
                cylinder(d = post_d, h = post_h);
                cylinder(d1 = post_d + skirt_flare, d2 = post_d, h = skirt_h);
            }
            // hollow, to save filament and print time; open at the top so
            // there is nothing to bridge
            translate([0, 0, skirt_h])
                cylinder(d = post_d - 2 * post_wall, h = post_h);
        }
    }
}

module arrow_tab() {
    // The tab is the arrow: a point, not a mark printed on a tab, so there is
    // nothing to mistake and nothing that disappears at a glance. Aim it at
    // the other sensor and the posts land at +/-90 degrees, clear of the
    // 145 degree wedge the sensor is actually watching.
    translate([0, outer_half - 6, deck_z])
        linear_extrude(floor_t)
            polygon([[-tab_w / 2, 0], [tab_w / 2, 0], [0, tab_len + 6]]);
    // a raised spine as well, so it reads by touch in a dim room
    translate([0, outer_half - 4, deck_z + floor_t - 0.01])
        linear_extrude(arrow_rise)
            polygon([[-tab_w / 2 + 5, 0], [tab_w / 2 - 5, 0], [0, tab_len]]);
}

module screw_holes() {
    for (x = [-screw_pitch, screw_pitch], y = [-screw_pitch, screw_pitch])
        translate([x, y, deck_z]) {
            translate([0, 0, -1]) cylinder(d = screw_clear, h = floor_t + 2);
            translate([0, 0, -0.01]) cylinder(d = screw_cbore, h = screw_cdepth);
        }
}

module calibration_target() {
    difference() {
        union() {
            plate();
            riser();
            cradle();
            arrow_tab();
            for (s = [-1, 1]) { arm(s); post(s); }
        }
        if (screws) screw_holes();
    }
}

show_sensor = false;   // -D show_sensor=true to see the C1 in place

calibration_target();
if (show_sensor) sensor_ghost();

// What it has to fit around, for looking at on screen only.
module sensor_ghost() {
    %translate([0, 0, deck_z + floor_t]) union() {
        linear_extrude(23.1) footprint();
        translate([0, 0, 23.1]) cylinder(d = 48.6, h = 41.3 - 23.1);
        translate([0, 0, laser_z - 0.5]) cylinder(d = 56, h = 1);  // the laser plane
    }
}
