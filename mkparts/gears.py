"""Gears as Blender objects, from `mkparts.geometry`. Runs inside Blender only; sizes in mm."""
from . import geometry as geo
import numpy as np

from .blender import MM, tagged_object


def herringbone_gear(name, N, m, b, beta, bore, mats, location=(0, 0, 0), phi_deg=20.0,
                     chamfer=None, n_z=24):
    """A herringbone gear of N teeth, module m, face width b and helix angle beta (degrees)
    with a plain bore, standing on its face at `location`. `mats` maps the face tags
    'outer' (teeth), 'inner' (bore) and 'end' (faces) to materials."""
    verts, faces, tags = geo.herringbone_gear(N, m, b, beta, bore, phi_deg, n_z, chamfer)
    return tagged_object(name, verts, faces, tags, mats, location, smooth_angle=25)


def helical_gear(name, N, m, b, beta, bore, mats, location=(0, 0, 0), phi_deg=20.0,
                 chamfer=None, n_z=24, z_cut=None):
    """A helical gear (beta in degrees, 0 for a spur gear) with a bore that is a diameter
    or a function r(theta) such as `geometry.keyed_bore`; `z_cut` cuts it there, the
    section taking mats['cut']."""
    verts, faces, tags = geo.helical_gear(N, m, b, beta, bore, phi_deg, n_z, chamfer,
                                          z_cut=z_cut)
    return tagged_object(name, verts, faces, tags, mats, location, smooth_angle=25)


def worm(name, m, q, starts, L, shaft_d, mats, shaft_L=(0.0, 0.0), location=(0, 0, 0),
         phi_deg=20.0):
    """A cylindrical worm with plain shaft ends, see `geometry.worm`. The thread crests
    cross the grid at a slant, so a sharp edge there renders as a saw tooth; the crest is
    shaded smooth into the flanks instead."""
    verts, faces, tags = geo.worm(m, q, starts, L, shaft_d, shaft_L, phi_deg)
    return tagged_object(name, verts, faces, tags, mats, location, smooth_angle=80)


def bevel_gear(name, N, m, delta, F, mats, spiral=0.0, depth=2.0, location=(0, 0, 0),
               phi_deg=20.0):
    """The toothed shell of a bevel gear, apex at the object origin, see
    `geometry.bevel_gear`; the body under it is built separately."""
    verts, faces, tags = geo.bevel_gear(N, m, delta, F, phi_deg, spiral, depth)
    return tagged_object(name, verts, faces, tags, mats, location, smooth_angle=30)


def keyed_shaft(name, d, b_key, h_key, z0, z1, mats, key_mat, key_z=None):
    """A shaft of diameter d from z0 to z1 with a parallel key b x h in a keyseat of depth
    h/2 on the +x side; the key spans key_z = (bottom, top). Returns the shaft and the key."""
    t1 = 0.55*h_key
    kz = key_z or (z0 + 4, z1 - 6)
    v, f, t = geo.keyed_shaft(d - 0.1, z1 - z0, b_key, t1, kz[0] - 1 - z0, kz[1] + 1 - z0)
    v[:, 2] += z0
    shaft = tagged_object(name, v, f, t, mats, smooth_angle=30)
    xk = d/2 - t1
    corners = [(xk, -b_key/2), (xk + h_key, -b_key/2), (xk + h_key, b_key/2), (xk, b_key/2)]
    v, f, t = geo.prism(corners, *kz)
    key = tagged_object(name + 'Key', v, f, t, {'outer': key_mat}, smooth_angle=30)
    mod = key.modifiers.new('bevel', 'BEVEL')
    mod.width, mod.segments = 0.4*MM, 2
    return shaft, key


def bevel_body(name, N, m, delta_deg, F, depth, d_bore, bk, hk, hub, mats, hub_side=None):
    """The body under a bevel gear's toothed shell: it fills the inner cone of the shell
    from the back to the front end and carries a hub (r, length) with a keyed bore. The hub
    stands on the front, towards the apex ('front', the default for a wheel, delta > 45°)
    or on the back ('back', the default for a pinion, and for the side gears of a
    differential, whose apex is taken by the other gears)."""
    d = np.radians(delta_deg)
    A0 = m*N/2/np.sin(d)
    h_in = -(1.25 + depth)*m
    back = geo.bevel_point(A0, h_in, 0.0, d)
    front = geo.bevel_point(A0 - F, h_in*(A0 - F)/A0, 0.0, d)
    # 0.2 mm inside the shell, so the two surfaces do not coincide and flicker
    R_b, z_b, R_f, z_f = back[0] - 0.2, back[2] - 0.2, front[0] - 0.2, front[2] - 0.2
    r_hub, l_hub = hub
    th = geo.theta_grid(360)
    if hub_side is None:
        hub_side = 'front' if delta_deg > 45 else 'back'
    if hub_side == 'front':                                        # a wheel: disc below, hub above
        z = [z_b - 6, z_b, z_f, z_f, z_f + l_hub]
        r = [R_b, R_b, R_f, r_hub, r_hub]
    elif delta_deg > 45:                                           # a flat gear with its hub behind
        z = [z_b - 6 - l_hub, z_b - 6, z_b - 6, z_b, z_f]
        r = [r_hub, r_hub, R_b, R_b, R_f]
    else:                                                          # a pinion: hub behind
        z = [z_b - l_hub, z_b, z_b, z_f]
        r = [r_hub, r_hub, R_b, R_f]
    bore = geo.keyed_bore(d_bore, bk, 0.5*hk + 0.2)(th)
    v, f, t = geo.radial_solid(th, z, np.repeat(np.asarray(r)[None, :], len(th), 0),
                               np.repeat(bore[:, None], len(z), 1))
    return tagged_object(name, v, f, t, mats, smooth_angle=30), (min(z), max(z))


def ring_gear(name, N, m, b, r_out, mats, beta=0.0, location=(0, 0, 0), phi_deg=20.0,
              chamfer=None, n_z=24):
    """An internal gear of N teeth in a rim of outer radius r_out, see `geometry.ring_gear`;
    a space is centred on the +x axis. `mats` maps 'outer' (rim), 'inner' (teeth) and
    'end' (faces)."""
    verts, faces, tags = geo.ring_gear(N, m, b, r_out, beta, phi_deg, n_z, chamfer)
    return tagged_object(name, verts, faces, tags, mats, location, smooth_angle=25)
