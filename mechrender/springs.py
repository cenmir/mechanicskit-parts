"""Springs as Blender objects: geometry from `mechrender.geometry`, solids from
`mechrender.blender`. Runs inside Blender only. All sizes in millimetres.
"""
from mathutils import Vector

from . import geometry as geo
from .blender import MM, cut_below_above, mesh, wire


def compression_spring(name, D, d, n_active, mat, p=None, ground=True, location=(0, 0, 0),
                       **kw):
    """A helical compression spring standing on z = 0 at `location`.

    Keyword arguments go to `geometry.compression_spring` (n_closed, cone, progressive,
    phase, height). Ground ends are cut flat a quarter wire deep, so the spring sits on its
    seat. Returns the object and its overall height in metres.
    """
    pts = geo.compression_spring(D, d, n_active, p=p, **kw)
    ob = wire(name, pts, d, mat)
    z_top = pts[-1, 2]
    if ground:
        cut_below_above(ob, d/4*MM, (z_top - d/4)*MM, D*MM)
        ob.location = (Vector(location) - Vector((0, 0, d/4)))*MM
        return ob, (z_top - d/2)*MM
    ob.location = Vector(location)*MM
    return ob, (z_top + d/2)*MM


def extension_spring(name, D, d, n, mat, location=(0, 0, 0)):
    """A close-wound extension spring with machine loops; returns object and body length (m)."""
    pts, L = geo.extension_spring(D, d, n)
    ob = wire(name, pts, d, mat)
    ob.location = Vector(location)*MM
    return ob, L*MM


def torsion_spring(name, D, d, n, leg, mat, location=(0, 0, 0), **kw):
    """A close-wound torsion spring with two tangential legs."""
    ob = wire(name, geo.torsion_spring(D, d, n, leg, **kw), d, mat)
    ob.location = Vector(location)*MM
    return ob


def disc_spring(name, De, Di, t, h0, mat, location=(0, 0, 0), flip=False):
    """A disc (Belleville) spring; flip alternate discs to stack them in series."""
    verts, faces = geo.revolve(geo.disc_spring_section(De, Di, t, h0, flip))
    ob = mesh(name, verts, faces, mat, bevel=0.12*t)
    ob.location = Vector(location)*MM
    return ob
