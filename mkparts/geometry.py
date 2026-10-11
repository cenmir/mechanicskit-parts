"""Parametric machine-element geometry as plain numpy arrays, in millimetres.

Nothing here imports Blender, so the same centre lines and sections can be plotted with
matplotlib, checked in a notebook, or handed to `mkparts.blender` to become solids.

Springs are described the way a spring maker describes them: mean coil diameter D, wire
diameter d, active coils n and pitch p. A wire is a centre line (an N x 3 array) that the
renderer sweeps with a circle of diameter d.
"""
import numpy as np

SAMPLES_PER_TURN = 120


# ---------------------------------------------------------------- helical compression springs
def pitch_profile(theta, n_total, p_active, d, n_closed=1.0, blend=0.35):
    """Height of the wire centre line at the winding angles `theta`.

    Each end has `n_closed` coils at pitch d, so they touch, blending smoothly into the
    active pitch over `blend` turns. The height is the integral of the local pitch per turn.
    """
    turns = theta/(2*np.pi)
    s0 = np.clip((turns - n_closed)/blend, 0, 1)
    s1 = np.clip((n_total - n_closed - turns)/blend, 0, 1)
    w = np.minimum(s0*s0*(3 - 2*s0), s1*s1*(3 - 2*s1))   # smoothstep at both ends
    p = d + (p_active - d)*w
    dz = p*np.gradient(turns)
    return np.cumsum(dz) - dz[0]


def free_height(d, n_active, p, n_closed=1.0):
    """Height of a spring with closed and ground ends, as `compression_spring` builds it.

    Grinding removes a quarter of the wire at each end, so the ground height equals the
    rise of the centre line.
    """
    n_total = n_active + 2*n_closed
    theta = np.linspace(0, 2*np.pi*n_total, int(SAMPLES_PER_TURN*n_total))
    return pitch_profile(theta, n_total, p, d, n_closed)[-1]


def pitch_for_height(H, d, n_active, n_closed=1.0):
    """Active pitch that gives a ground spring the height H, e.g. a compressed state."""
    # The height is affine in the active pitch, so two evaluations fix the line.
    h1, h2 = free_height(d, n_active, 1.0, n_closed), free_height(d, n_active, 2.0, n_closed)
    return 1.0 + (H - h1)/(h2 - h1)


def compression_spring(D, d, n_active, p=None, n_closed=1.0, cone=0.0, progressive=0.0,
                       phase=0.0, height=None):
    """Centre line of a helical compression spring standing on z = 0.

    Parameters
    ----------
    D, d : mean coil diameter and wire diameter.
    n_active : active coils. `n_closed` closed coils are added at each end.
    p : active pitch. Give `height` instead to set the overall (ground) height directly.
    cone : relative change of coil diameter from bottom to top, for a conical spring.
    progressive : relative change of active pitch from bottom to top, for variable pitch.
    phase : rotation of the start of the wire about the axis, in radians.

    Returns
    -------
    pts : (N, 3) array, the wire centre line. The lowest point is at z = d/2.
    """
    if height is not None:
        p = pitch_for_height(height, d, n_active, n_closed)
    n_total = n_active + 2*n_closed
    theta = np.linspace(0, 2*np.pi*n_total, int(SAMPLES_PER_TURN*n_total))
    turns = theta/(2*np.pi)
    if progressive:
        # Local active pitch grows linearly along the spring, so the coils close one by one.
        pa = p*(1 - progressive/2 + progressive*turns/n_total)
        z = pitch_profile(theta, n_total, 1.0, d, n_closed)
        w = (np.gradient(z)/np.gradient(turns) - d)/(1.0 - d)
        dz = (d + (pa - d)*w)*np.gradient(turns)
        z = np.cumsum(dz) - dz[0]
    else:
        z = pitch_profile(theta, n_total, p, d, n_closed)
    R = D/2*(1 + cone*(turns/n_total - 0.5))
    return np.c_[R*np.cos(theta + phase), R*np.sin(theta + phase), z + d/2]


# ---------------------------------------------------------------- extension and torsion springs
def _loop(p_end, D, sgn):
    # From the end of the last coil, bend in to the axis, then a full loop in the xz plane.
    R = D/2
    x0, y0, z0 = p_end
    t = np.linspace(0, 1, 30)[1:]
    bend = np.c_[x0*(1 - t), y0*(1 - t), z0 + sgn*R*0.9*np.sin(np.pi*t/2)]
    zc = z0 + sgn*(0.9*R + R)
    phi = np.linspace(0, 2*np.pi - 0.35, 200)
    ring = np.c_[R*np.sin(phi)*-sgn, np.zeros_like(phi), zc - sgn*R*np.cos(phi)]
    return np.r_[bend, ring]


def extension_spring(D, d, n):
    """Close-wound extension spring along z with a machine loop at each end.

    Returns the centre line and the length of the close-wound body.
    """
    theta = np.linspace(0, 2*np.pi*n, int(SAMPLES_PER_TURN*n))
    body = np.c_[D/2*np.cos(theta), D/2*np.sin(theta), d*theta/(2*np.pi)]
    pts = np.r_[_loop(body[0], D, -1)[::-1], body, _loop(body[-1], D, +1)]
    return pts, body[-1, 2]


def torsion_spring(D, d, n, leg, angle=np.radians(90)):
    """Close-wound torsion spring along z with two straight tangential legs of length `leg`.

    `angle` is the extra winding beyond n full turns, which sets the angle between the legs.
    """
    theta = np.linspace(0, 2*np.pi*n + angle, int(SAMPLES_PER_TURN*n))
    coil = np.c_[D/2*np.cos(theta), D/2*np.sin(theta), d*theta/(2*np.pi)]

    def straight(p, th, sgn):
        tangent = np.array([-np.sin(th), np.cos(th), 0])*sgn
        s = np.linspace(0, leg, 20)[1:]
        return p + s[:, None]*tangent

    return np.r_[straight(coil[0], theta[0], -1)[::-1], coil, straight(coil[-1], theta[-1], +1)]


# ---------------------------------------------------------------- solids of revolution
def disc_spring_section(De, Di, t, h0, flip=False):
    """Section of a disc (Belleville) spring in the (r, z) plane, as a closed quadrilateral.

    The inner edge rests on z = 0 (or the outer edge, when flipped), so alternately flipped
    discs stack edge to edge, i.e. in series.
    """
    s = -1.0 if flip else 1.0
    sec = np.array([(Di/2, 0), (De/2, -s*h0), (De/2, -s*h0 + t), (Di/2, t)])
    if flip:
        sec[:, 1] += h0
    return sec


def revolve(section, n=160):
    """Revolve a closed (r, z) polygon about the z axis into a quad mesh.

    Returns vertices (M, 3) and faces (list of 4-tuples) for any mesh library.
    """
    k = len(section)
    phi = np.linspace(0, 2*np.pi, n, endpoint=False)
    verts = np.array([(r*np.cos(a), r*np.sin(a), z) for a in phi for r, z in section])
    faces = [(k*i + j, k*i + (j + 1) % k, k*((i + 1) % n) + (j + 1) % k, k*((i + 1) % n) + j)
             for i in range(n) for j in range(k)]
    return verts, faces


# ---------------------------------------------------------------- star-shaped solids: threads, hexagons, blocks
def radial_solid(theta, z, r_out, r_in=None, closed=None):
    """Mesh of a solid whose surface is r = r_out(theta, z) about the z axis, optionally
    hollow with a bore r = r_in(theta, z).

    theta (n,) and z (m,) are the grid; r_out and r_in are (n, m) arrays, so any part that
    is star-shaped about its axis (threaded rods, hexagon heads and nuts, a block with a
    hole) is one call. z may repeat a value to make a step. `closed` defaults to whether
    theta spans a full turn; an open theta range gives a section, with flat cut faces in
    the planes theta[0] and theta[-1].

    Returns vertices (M, 3), faces, and a tag per face: 'outer', 'inner', 'end' or 'cut'.
    Face orientation is left to the consumer (Blender recalculates normals).
    """
    theta, z = np.asarray(theta, float), np.asarray(z, float)
    n, m = len(theta), len(z)
    if closed is None:
        closed = np.isclose(theta[-1] - theta[0], 2*np.pi) or theta[-1] - theta[0] > 2*np.pi
    if closed and np.isclose(theta[-1] - theta[0], 2*np.pi):
        theta, r_out = theta[:-1], np.asarray(r_out)[:-1]
        r_in = None if r_in is None else np.asarray(r_in)[:-1]
        n -= 1
    c, s = np.cos(theta)[:, None], np.sin(theta)[:, None]
    zz = np.broadcast_to(z, (n, m))

    def ring(r):
        return np.stack([r*c, r*s, zz], -1).reshape(-1, 3)

    verts = [ring(np.asarray(r_out))]
    O = lambda i, j: i*m + j                                   # noqa: E731
    if r_in is not None:
        verts.append(ring(np.asarray(r_in)))
        X = lambda i, j: n*m + i*m + j                         # noqa: E731
    else:
        verts.append(np.c_[np.zeros(m), np.zeros(m), z])
        X = lambda i, j: n*m + j                               # noqa: E731  the axis
    faces, tags = [], []
    span = range(n) if closed else range(n - 1)
    for i in span:
        k = (i + 1) % n
        for j in range(m - 1):
            faces.append((O(i, j), O(k, j), O(k, j + 1), O(i, j + 1)))
            tags.append('outer')
            if r_in is not None:
                faces.append((X(i, j), X(i, j + 1), X(k, j + 1), X(k, j)))
                tags.append('inner')
        for j in (0, m - 1):
            f = (O(i, j), X(i, j), X(k, j), O(k, j)) if r_in is not None else (O(i, j), X(i, j), O(k, j))
            faces.append(f)
            tags.append('end')
    if not closed:
        for i in (0, n - 1):
            for j in range(m - 1):
                faces.append((O(i, j), O(i, j + 1), X(i, j + 1), X(i, j)))
                tags.append('cut')
    return np.concatenate(verts), faces, tags


def iso_thread_radius(u, P, d, d1):
    """Radius of the ISO 68-1 basic profile at the axial phase u (mm from a root centre).

    The profile has a flat of P/4 at the minor diameter d1 and of P/8 at the major diameter
    d, joined by straight flanks at 30 degrees to the radial direction. It bounds both the
    external and the internal thread, from opposite sides.
    """
    t = np.mod(u, P)
    s = np.minimum(t, P - t)                                   # distance from the root centre
    a, b = P/8, P/2 - P/16
    return d1/2 + (d/2 - d1/2)*np.clip((s - a)/(b - a), 0, 1)


def helical_phase(theta, z, P):
    """Axial phase of a right-hand single-start thread: constant along the helix
    z = u + P theta/(2 pi)."""
    return z - P*theta/(2*np.pi)


def hexagon_radius(theta, s):
    """Radius of a regular hexagon with width across flats s, corners at theta = k 60 deg."""
    return (s/2)/np.cos(np.mod(theta, np.pi/3) - np.pi/6)


def square_radius(theta, w):
    """Radius of a square of side w centred on the axis, sides parallel to x and y."""
    return (w/2)/np.maximum(np.abs(np.cos(theta)), np.abs(np.sin(theta)))


def theta_grid(n=240, start=0.0, stop=2*np.pi, corners=()):
    """Angles for radial_solid: n even steps plus exact corner angles (e.g. a hexagon's)."""
    th = np.r_[np.linspace(start, stop, n + 1),
               [a for a in np.mod(corners, 2*np.pi) if start < a < stop]]
    return np.unique(np.round(th, 12))


def iso_metric(d):
    """Coarse-pitch ISO metric thread M d (ISO 261/724): pitch P, pitch diameter d2,
    basic minor diameter d1 and tensile stress diameter, all in mm."""
    P = {3: 0.5, 4: 0.7, 5: 0.8, 6: 1.0, 8: 1.25, 10: 1.5, 12: 1.75, 14: 2.0, 16: 2.0,
         20: 2.5, 24: 3.0, 30: 3.5, 36: 4.0}[d]
    H = np.sqrt(3)/2*P
    d2, d1 = d - 0.75*H, d - 1.25*H
    d3 = d1 - H/6
    return dict(d=d, P=P, H=H, d2=d2, d1=d1, d3=d3, As=np.pi/4*((d2 + d3)/2)**2)


def hex_bolt(d, L, b, s, k, dw, theta, dz=None):
    """Hexagon head bolt (ISO 4014/4017 proportions) as radial_solid arrays.

    Thread M d over the length b from the tip at z = 0, plain shank up to the head at
    z = L, head of width across flats s and height k with a 30 degree top chamfer and a
    washer face of diameter dw. Returns (z, r_out) for radial_solid with the given theta.
    """
    t = iso_metric(d)
    P, d1 = t['P'], t['d1']
    dz = dz or P/20
    z_sh = np.arange(0, L + dz/2, dz)
    z_hd = np.r_[L, L + 0.4, np.linspace(L + 0.4, L + k, max(8, int(k/dz/2)))]
    th = theta[:, None]
    rt = iso_thread_radius(helical_phase(th, z_sh[None, :], P), P, d, d1)
    run = np.clip((z_sh - (b - 1.5*P))/(1.5*P), 0, 1)          # thread runout into the shank
    rt = np.maximum(rt, d1/2 + (d/2 - d1/2)*run*run*(3 - 2*run))
    rt = np.minimum(rt, d1/2 - 0.3 + z_sh)                      # 45 degree chamfer at the tip
    hx = np.minimum(hexagon_radius(th, s), dw/2*1.02 + (L + k - z_hd)*np.tan(np.radians(60)))
    hx[:, 0:2] = np.minimum(hexagon_radius(theta, s), dw/2)[:, None]   # washer face, 0.4 mm
    return np.r_[z_sh, z_hd], np.c_[rt, hx]


def hex_nut(d, m_, s, z0, theta, clearance=0.06, dz=None):
    """Hexagon nut (ISO 4032 proportions) of height m_ from z0, as radial_solid arrays.

    The bore is the same ISO 68-1 helix as the bolt, opened by `clearance` (mm) so the two
    surfaces do not coincide, with 120 degree countersinks and 30 degree outer chamfers at
    both faces. Returns (z, r_out, r_in).
    """
    t = iso_metric(d)
    P, d1 = t['P'], t['d1']
    dz = dz or P/20
    z = np.arange(z0, z0 + m_ + dz/2, dz)
    th = theta[:, None]
    e = np.minimum(z - z0, z0 + m_ - z)[None, :]                # distance to the nearer face
    r_in = iso_thread_radius(helical_phase(th, z[None, :], P), P, d, d1) + clearance
    r_in = np.maximum(r_in, 0.54*d - e*np.tan(np.radians(60)))
    r_out = np.minimum(hexagon_radius(th, s), 0.95*s/2 + e*np.tan(np.radians(60)))
    return z, r_out, r_in


# ---------------------------------------------------------------- gears
def spur_outline(N, m, phi_deg=20.0, n_flank=40, n_land=6):
    """Closed outline of an involute spur gear in polar form, a tooth centred on theta = 0.

    Returns (theta, r): theta rises monotonically over one turn from -pi/N, so the outline
    is star-shaped and fits `radial_solid`. Below the base circle the flank continues as a
    radial line (two points at the same theta), which keeps gears with few teeth valid.
    """
    phi = np.radians(phi_deg)
    rp = m*N/2
    rb, ra, rf = rp*np.cos(phi), rp + m, rp - 1.25*m
    t_tip = np.sqrt((ra/rb)**2 - 1)
    t = np.linspace(0, t_tip, n_flank)
    x, y = rb*(np.sin(t) - t*np.cos(t)), rb*(np.cos(t) + t*np.sin(t))
    r_inv, th_inv = np.hypot(x, y), np.arctan2(x, y)            # angle from the start of the involute
    a_p = np.sqrt((rp/rb)**2 - 1)
    inv_p = a_p - np.arctan(a_p)                                  # involute function at the pitch circle
    half = np.pi/(2*N) + inv_p                                    # flank start angle from the tooth axis
    keep = r_inv >= rf
    r_fl, th_fl = r_inv[keep], half - th_inv[keep]                # left flank, root to tip, theta > 0
    if rf < rb:                                                    # radial line from the root to the base
        r_fl, th_fl = np.r_[rf, r_fl], np.r_[half, th_fl]
    th_tip = np.linspace(-th_fl[-1], th_fl[-1], n_land)[1:-1]
    th_root = np.linspace(th_fl[0], 2*np.pi/N - th_fl[0], n_land)[1:-1]
    th_one = np.r_[-th_fl, th_tip, th_fl[::-1], th_root]          # root, right flank, tip, left flank
    r_one = np.r_[r_fl, np.full(len(th_tip), ra), r_fl[::-1], np.full(len(th_root), rf)]
    pitch = 2*np.pi/N
    theta = np.concatenate([th_one + k*pitch for k in range(N)])
    radius = np.tile(r_one, N)
    return theta, radius


def herringbone_gear(N, m, b, beta_deg, bore, phi_deg=20.0, n_z=24, chamfer=None):
    """Herringbone gear: the spur outline of N teeth, module m, face width b (mm), twisted
    by the helix angle beta in a V about the mid-plane, with a plain bore of diameter `bore`.

    A section at height z is the spur outline turned by tan(beta)|z - b/2|/r_p, so each half
    is a helical gear of opposite hand and the axial forces cancel. `chamfer` (mm) breaks
    the tip edges at both faces. Returns vertices, faces and tags as `radial_solid`, with
    the gear from z = 0 to b.
    """
    th, r = spur_outline(N, m, phi_deg)
    rp = m*N/2
    z = np.unique(np.r_[np.linspace(0, b, n_z + 1), b/2])
    r_out = np.repeat(r[:, None], len(z), 1)
    if chamfer:
        e = np.minimum(z, b - z)[None, :]
        r_out = np.minimum(r_out, rp + m - chamfer + e)
    r_in = np.full_like(r_out, bore/2)
    verts, faces, tags = radial_solid(np.r_[th, th[0] + 2*np.pi], z,
                                      np.r_[r_out, r_out[:1]], np.r_[r_in, r_in[:1]])
    twist = np.tan(np.radians(beta_deg))*np.abs(verts[:, 2] - b/2)/rp
    c, s = np.cos(twist), np.sin(twist)
    verts = np.c_[c*verts[:, 0] - s*verts[:, 1], s*verts[:, 0] + c*verts[:, 1], verts[:, 2]]
    return verts, faces, tags
