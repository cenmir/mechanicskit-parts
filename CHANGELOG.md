# Changelog

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
