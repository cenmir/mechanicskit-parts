"""Bolts, nuts and clamped plates as Blender objects, from `mkparts.geometry`.
Runs inside Blender only. All sizes in millimetres.

Every part is a `geometry.radial_solid`, so the same call gives the whole part or a
section: pass theta from 0 to pi to keep the half y >= 0, cut in the xz plane.
"""
import bpy
import numpy as np

from . import geometry as geo
from .blender import MM, tagged_object


def radial_object(name, theta, z, r_out, mats, r_in=None, location=(0, 0, 0), smooth_angle=20):
    """A Blender mesh from radial_solid arrays. `mats` maps a face tag ('outer', 'inner',
    'end', 'cut') to a material; missing tags use the 'outer' one."""
    verts, faces, tags = geo.radial_solid(theta, z, r_out, r_in)
    return tagged_object(name, verts, faces, tags, mats, location, smooth_angle)


def text_mark(name, body, size, depth, location, mat, rotation=(0, 0, 0)):
    """Raised lettering, e.g. a property class on a bolt head; sizes in mm."""
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body, cu.size, cu.extrude = body, size*MM, depth/2*MM
    cu.align_x, cu.align_y = 'CENTER', 'CENTER'
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    ob.location = tuple(np.asarray(location)*MM)
    ob.rotation_euler = rotation
    ob.data.materials.append(mat)
    return ob
