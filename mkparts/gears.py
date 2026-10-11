"""Gears as Blender objects, from `mkparts.geometry`. Runs inside Blender only; sizes in mm."""
from . import geometry as geo
from .blender import tagged_object


def herringbone_gear(name, N, m, b, beta, bore, mats, location=(0, 0, 0), phi_deg=20.0,
                     chamfer=None, n_z=24):
    """A herringbone gear of N teeth, module m, face width b and helix angle beta (degrees)
    with a plain bore, standing on its face at `location`. `mats` maps the face tags
    'outer' (teeth), 'inner' (bore) and 'end' (faces) to materials."""
    verts, faces, tags = geo.herringbone_gear(N, m, b, beta, bore, phi_deg, n_z, chamfer)
    return tagged_object(name, verts, faces, tags, mats, location, smooth_angle=25)
