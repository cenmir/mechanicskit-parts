# Changelog

## [0.4.0] - 2026-10-11

### Added

- `geometry`: shaft couplings. `fork` and `cross` of a Hooke joint; `spline_shaft` and
  `spline_bore`, the ISO 4156 involute spline (30 degrees, flat root) and its hub;
  `spherical_shell` for the bell of a ball joint; `jaw_hub` and `spider` of a jaw
  coupling; and the helpers they are built from: `merge` and `place` to assemble and move
  parts, `cylinder`, `slot` (a bar with round ends), `annular_sector`.
- `spur_tooth` and `spur_outline` take the addendum and dedendum factors `ha` and `hf`
  (1 and 1.25 for gears; 0.5 and 0.75 for a spline shaft).

## [0.3.2] - 2026-10-11

### Added

- `geometry.helical_gear` and `gears.helical_gear` take `z_cut`: the gear cut across its
  thickness at that depth, the section tagged 'cut' (a spur outline turned by the helix).

## [0.3.1] - 2026-10-11

### Changed

- `gears.bevel_body` takes `hub_side` ('front' or 'back'), so the side gears of a
  differential can carry their hub outwards while their cone is that of a wheel.

## [0.3.0] - 2026-10-11

### Added

- `geometry`: `spur_tooth` (one involute tooth, fractional N allowed) with an optional
  root fillet, also through `spur_outline(fillet=...)`; `helical_gear`; the cylindrical
  `worm`; the spiral or straight `bevel_gear` shell on Tredgold's virtual spur gear, with
  `bevel_point`; bores and shafts with keys (`keyed_bore`, `keyseat_radius`,
  `keyed_shaft`), a `keyhole`, and flat parts (`ribbon`, `prism`) from the ray helpers
  `convex_exit` and `convex_entry`.
- `gears`: helical gears, worms, bevel gear shells and their bodies (`bevel_body`), and
  a shaft with a parallel key (`keyed_shaft`), as Blender objects.
- `blender`: `pivot` and `adopt`, an empty that turns a gear with its shaft and key about
  the gear's own axis; `paint_stripe`, a painted radius that turns with it.

### Changed

- `geometry.herringbone_gear` takes a bore function as well as a diameter, and a
  `fillet`; the bore is no longer twisted with the teeth.

## [0.2.0] - 2026-10-11

### Added

- `geometry`: star-shaped solids (`radial_solid`, `theta_grid`), the ISO 68-1 thread
  (`iso_thread_radius`, `helical_phase`, `iso_metric`), hexagon bolts and nuts
  (`hex_bolt`, `hex_nut`, `hexagon_radius`, `square_radius`), and gears
  (`spur_outline`, the involute outline in polar form, and `herringbone_gear`).
- `fasteners`: bolts, nuts and plates as Blender objects, whole or in section; raised
  lettering (`text_mark`).
- `gears`: herringbone gears as Blender objects.
- `blender`: `tagged_object` (a mesh with a material per face tag, flat-shaded plane
  faces), `hatched` section materials, and `heat_steel` / `heat_node` for showing a part's
  temperature by colour in heating and cooling animations.

## [0.1.0] - 2026-10-06

First release: spring geometry, Blender scene helpers and remote GPU rendering.
