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
def spur_tooth(N, m, phi_deg=20.0, n_flank=40, n_land=6, fillet=None, ha=1.0, hf=1.25):
    """One tooth of an involute spur gear in polar form, (theta, r), centred on theta = 0 and
    running from -pi/N (the middle of the space before it) towards +pi/N.

    N may be fractional, for the virtual spur gear of a bevel gear. Below the base circle the
    flank continues as a radial line (two points at the same theta). `fillet` (mm) rounds the
    corner where that line meets the root circle with an arc tangent to both; it needs a
    root circle inside the base circle, about N < 42 at 20 degrees. The addendum and
    dedendum are ha*m and hf*m, 1 and 1.25 for a gear; a 30 degree flat-root spline shaft
    of ISO 4156 has 0.5 and 0.75.
    """
    phi = np.radians(phi_deg)
    rp = m*N/2
    rb, ra, rf = rp*np.cos(phi), rp + ha*m, rp - hf*m
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
    if fillet:
        # circle of radius R tangent to the root circle and to the radial line theta = half:
        # centre at radius rf + R, turned by delta into the space
        R = fillet
        r_t = np.sqrt(rf**2 + 2*rf*R)                             # where it leaves the radial line
        if rf >= rb or r_t >= rb:
            raise ValueError(f'a root fillet of {R} mm does not fit below the base circle of N = {N}')
        delta = np.arcsin(R/(rf + R))
        cx, cy = (rf + R)*np.cos(half + delta), (rf + R)*np.sin(half + delta)
        a0 = np.arctan2(-cy, -cx)                                 # towards the root-circle tangent point
        a1 = np.arctan2(r_t*np.sin(half) - cy, r_t*np.cos(half) - cx)
        a1 = a0 + (a1 - a0 + np.pi) % (2*np.pi) - np.pi
        a = np.linspace(a0, a1, 10)
        xa, ya = cx + R*np.cos(a), cy + R*np.sin(a)
        r_fl, th_fl = np.r_[np.hypot(xa, ya), r_fl[1:]], np.r_[np.arctan2(ya, xa), th_fl[1:]]
    th_tip = np.linspace(-th_fl[-1], th_fl[-1], n_land)[1:-1]
    th_root = np.linspace(th_fl[0], 2*np.pi/N - th_fl[0], n_land)[1:-1]
    th_one = np.r_[-th_fl, th_tip, th_fl[::-1], th_root]          # root, right flank, tip, left flank
    r_one = np.r_[r_fl, np.full(len(th_tip), ra), r_fl[::-1], np.full(len(th_root), rf)]
    return th_one, r_one


def spur_outline(N, m, phi_deg=20.0, n_flank=40, n_land=6, fillet=None, ha=1.0, hf=1.25):
    """Closed outline of an involute spur gear in polar form, a tooth centred on theta = 0.

    Returns (theta, r): theta rises monotonically over one turn from -pi/N, so the outline
    is star-shaped and fits `radial_solid`. Below the base circle the flank continues as a
    radial line (two points at the same theta), which keeps gears with few teeth valid;
    `fillet` rounds its corner at the root (see `spur_tooth`).
    """
    th_one, r_one = spur_tooth(N, m, phi_deg, n_flank, n_land, fillet, ha, hf)
    pitch = 2*np.pi/N
    theta = np.concatenate([th_one + k*pitch for k in range(N)])
    radius = np.tile(r_one, N)
    return theta, radius


def _gear_solid(N, m, b, bore, twist, phi_deg, n_z, chamfer, fillet, z_cut=None):
    """Spur outline extruded over 0 <= z <= b and turned by twist(z) (radians at the pitch
    circle); the bore is a diameter or a function r(theta) (a keyway, a keyhole) and is not
    turned, so a keyway stays straight in a helical gear. With z_cut the gear ends at that
    height, a section, and the faces there are tagged 'cut'."""
    th, r = spur_outline(N, m, phi_deg, fillet=fillet)
    rp = m*N/2
    z = np.unique(np.r_[np.linspace(0, b, n_z + 1), b/2])
    if z_cut is not None:
        z = np.unique(np.r_[z[z < z_cut - 1e-9], z_cut])
    r_out = np.repeat(r[:, None], len(z), 1)
    if chamfer:
        e = np.minimum(z, b - z)[None, :]
        r_out = np.minimum(r_out, rp + m - chamfer + e)
    th_c = np.r_[th, th[0] + 2*np.pi]
    r_b = bore(th_c) if callable(bore) else np.full(len(th_c), bore/2)
    r_in = np.repeat(np.asarray(r_b, float)[:, None], len(z), 1)
    verts, faces, tags = radial_solid(th_c, z, np.r_[r_out, r_out[:1]], r_in)
    n_out = len(verts)//2                                         # the toothed surface comes first
    a = twist(verts[:n_out, 2])
    c, s = np.cos(a), np.sin(a)
    x, y = verts[:n_out, 0].copy(), verts[:n_out, 1].copy()
    verts[:n_out, 0], verts[:n_out, 1] = c*x - s*y, s*x + c*y
    if z_cut is not None:
        tags = ['cut' if t == 'end' and np.allclose(verts[list(f), 2], z_cut) else t
                for f, t in zip(faces, tags)]
    return verts, faces, tags


def herringbone_gear(N, m, b, beta_deg, bore, phi_deg=20.0, n_z=24, chamfer=None, fillet=None):
    """Herringbone gear: the spur outline of N teeth, module m, face width b (mm), twisted
    by the helix angle beta in a V about the mid-plane, with a bore of diameter `bore` (or
    a function r(theta), see `keyed_bore`).

    A section at height z is the spur outline turned by tan(beta)|z - b/2|/r_p, so each half
    is a helical gear of opposite hand and the axial forces cancel. `chamfer` (mm) breaks
    the tip edges at both faces. Returns vertices, faces and tags as `radial_solid`, with
    the gear from z = 0 to b.
    """
    k = np.tan(np.radians(beta_deg))/(m*N/2)
    return _gear_solid(N, m, b, bore, lambda z: k*np.abs(z - b/2), phi_deg, n_z, chamfer, fillet)


def helical_gear(N, m, b, beta_deg, bore, phi_deg=20.0, n_z=24, chamfer=None, fillet=None,
                 z_cut=None):
    """Helical gear of N teeth, transverse module m, face width b and helix angle beta
    (degrees; positive is right-hand), from z = 0 to b. beta = 0 is a spur gear. The bore
    is a diameter or a function r(theta). `z_cut` cuts the gear at that height, keeping
    0 <= z <= z_cut: the section shows the spur outline turned by the helix. Returns
    vertices, faces and tags ('cut' on the section)."""
    k = np.tan(np.radians(beta_deg))/(m*N/2)
    return _gear_solid(N, m, b, bore, lambda z: k*(z - b/2), phi_deg, n_z, chamfer, fillet,
                       z_cut)


def worm(m, q, starts, L, shaft_d, shaft_L=(0.0, 0.0), phi_deg=20.0, n_theta=400,
         per_pitch=56):
    """Cylindrical worm of axial module m, diameter quotient q (pitch diameter q m) and
    `starts` threads over the length L, right-hand, from z = 0 to L, with plain shaft ends
    of diameter `shaft_d` and lengths shaft_L = (below, above).

    The axial section is the straight-sided rack of the wheel: thread thickness pi m/2 on
    the pitch line, flanks at the pressure angle, addendum m, dedendum 1.25 m; over the
    last pitch at each end the threads run out to the root. Returns vertices, faces and tags.
    """
    p = np.pi*m
    lead = starts*p
    r1 = q*m/2
    ra, rf = r1 + m, r1 - 1.25*m
    tphi = np.tan(np.radians(phi_deg))
    th = theta_grid(n_theta)
    lo, hi = shaft_L
    zt = np.linspace(0, L, int(round(L/p*per_pitch)) + 1)
    # each end plane appears twice, once for the shaft and once for the worm: a step
    z = np.r_[np.linspace(-lo, 0, 6) if lo else [], zt, np.linspace(L, L + hi, 6) if hi else []]
    on_shaft = np.r_[np.ones(6 if lo else 0, bool), np.zeros(len(zt), bool),
                     np.ones(6 if hi else 0, bool)]
    T, Z = np.meshgrid(th, z, indexing='ij')
    u = np.mod(Z - lead*T/(2*np.pi) + p/2, p) - p/2              # axial phase from a thread centre
    r = np.clip(r1 + (p/4 - np.abs(u))/tphi, rf, ra)
    run = np.clip(np.minimum(Z, L - Z)/p, 0, 1)                   # runout over the end pitches
    r = np.minimum(r, rf + (ra - rf)*run)
    r = np.where(on_shaft[None, :], shaft_d/2, r)
    return radial_solid(th, z, r)


def bevel_gear(N, m, delta_deg, F, phi_deg=20.0, spiral_deg=0.0, depth=2.0, n_rho=24):
    """Toothed shell of a bevel gear: N teeth, module m at the back (outer) end, pitch cone
    angle delta, face width F along the cone, spiral angle `spiral_deg` at mid face (0 is
    a straight bevel gear; positive is right-hand).

    The axis is z, with the cone apex at the origin and the gear below it. At the cone
    distance rho the teeth are the virtual spur gear of N/cos(delta) teeth (Tredgold's
    approximation), scaled by rho/A0, set out along the normal to the pitch cone, so every
    tooth line runs to the apex. The teeth stand on a shell `depth` modules deep below the
    root; the body under it (hub, web, bore) is a separate part: see `bevel_point`.
    A spiral tooth follows a logarithmic spiral on the pitch cone. Returns vertices, faces
    and tags ('outer' teeth, 'inner' underside, 'end' back and front cones).
    """
    d = np.radians(delta_deg)
    A0 = m*N/2/np.sin(d)                                          # outer cone distance
    Nv = N/np.cos(d)
    th_v, r_v = spur_tooth(Nv, m, phi_deg)
    pitch = 2*np.pi/N
    th = np.concatenate([th_v*np.cos(d)**-1 + k*pitch for k in range(N)])
    # th_v spans 2 pi/Nv per tooth, which maps onto 2 pi/N
    h = np.tile(r_v - m*Nv/2, N)                                  # height above the pitch cone
    rho = np.linspace(A0 - F, A0, n_rho + 1)
    R0 = 10*m*(depth + 2)                                         # keeps the stand-in radius positive
    th_c = np.r_[th, th[0] + 2*np.pi]
    r_out = np.repeat(np.r_[h, h[:1]][:, None] + R0, len(rho), 1)
    r_in = np.full_like(r_out, R0 - (1.25 + depth)*m)
    verts, faces, tags = radial_solid(th_c, rho, r_out, r_in)
    a = np.arctan2(verts[:, 1], verts[:, 0])
    hh, rr = np.hypot(verts[:, 0], verts[:, 1]) - R0, verts[:, 2]
    a = a + np.tan(np.radians(spiral_deg))*np.log(rr/(A0 - F/2))/np.sin(d)
    verts = bevel_point(rr, hh*rr/A0, a, d)
    return verts, faces, tags


def bevel_point(rho, h, theta, delta):
    """Point at the cone distance rho from the apex (origin) of a cone of half angle delta
    (radians) about -z, raised h along the cone's outward normal, at the angle theta."""
    rho, h, theta = np.broadcast_arrays(rho, h, theta)
    rad = rho*np.sin(delta) + h*np.cos(delta)
    z = -rho*np.cos(delta) + h*np.sin(delta)
    return np.stack([rad*np.cos(theta), rad*np.sin(theta), z], -1)


# ---------------------------------------------------------------- bores, keyways, keyholes
def convex_exit(theta, poly):
    """Distance along the ray from the origin at the angle theta to where it leaves the
    convex polygon `poly` (k x 2, counter-clockwise), which holds the origin inside or on
    an edge; 0 for rays that point away from it."""
    d = np.stack([np.cos(theta), np.sin(theta)], -1)
    p0 = np.asarray(poly, float)
    e = np.roll(p0, -1, 0) - p0
    nrm = np.stack([e[:, 1], -e[:, 0]], -1)                       # outward edge normals
    num, den = (nrm*p0).sum(1), d @ nrm.T
    with np.errstate(divide='ignore', invalid='ignore'):
        t = np.where(den > 1e-12, num/den, np.inf).min(1)
    return np.where(np.isfinite(t), np.maximum(t, 0), 0.0)


def convex_entry(theta, poly):
    """Distance along the ray from the origin at the angle theta to where it enters the
    convex polygon `poly` (counter-clockwise) outside the origin; inf where it misses."""
    d = np.stack([np.cos(theta), np.sin(theta)], -1)
    p0 = np.asarray(poly, float)
    e = np.roll(p0, -1, 0) - p0
    nrm = np.stack([e[:, 1], -e[:, 0]], -1)
    num, den = (nrm*p0).sum(1), d @ nrm.T
    with np.errstate(divide='ignore', invalid='ignore'):
        q = num/den
        t_in = np.where(den < -1e-12, q, -np.inf).max(1)
        t_out = np.where(den > 1e-12, q, np.inf).min(1)
    t_in = np.maximum(t_in, 0)
    return np.where(t_in <= t_out, t_in, np.inf)


def keyed_bore(d, b, t2):
    """r(theta) of a hub bore of diameter d with a keyway of width b and depth t2 (above
    the bore, at its edge) on the +x side."""
    rect = [(0, -b/2), (d/2 + t2, -b/2), (d/2 + t2, b/2), (0, b/2)]
    return lambda th: np.maximum(d/2, convex_exit(np.asarray(th, float), rect))


def keyseat_radius(theta, d, b, t1):
    """Radius of a shaft of diameter d with a keyseat of width b and depth t1 on the +x side."""
    rect = [(d/2 - t1, -b/2), (2*d, -b/2), (2*d, b/2), (d/2 - t1, b/2)]
    return np.minimum(d/2, convex_entry(np.asarray(theta, float), rect))


def keyed_shaft(d, L, b, t1, z0, z1, chamfer=1.0, n=240):
    """Shaft of diameter d from z = 0 to L with a keyseat of width b and depth t1 on the +x
    side between z0 and z1 (flat ends), and chamfered ends. Returns vertices, faces, tags."""
    th = theta_grid(n, corners=[np.arcsin(b/d), -np.arcsin(b/d),
                                np.arctan2(b/2, d/2 - t1), -np.arctan2(b/2, d/2 - t1)])
    r_k = keyseat_radius(th, d, b, t1)[:, None]
    z = np.r_[0, chamfer, z0, z0, z1, z1, L - chamfer, L]
    r = np.repeat(np.full(len(z), d/2)[None, :], len(th), 0)
    r[:, [0, -1]] = d/2 - chamfer
    r[:, 3:5] = r_k
    return radial_solid(th, z, r)


def keyhole(a, w1, w2, L):
    """r(theta) of a keyhole: a circle of radius a with a slot from width w1 at the centre to
    w2 at the distance L on the -y side."""
    trap = [(-w1/2, 0), (-w2/2, -L), (w2/2, -L), (w1/2, 0)]
    return lambda th: np.maximum(a, convex_exit(np.asarray(th, float), trap))


def ribbon(path, w):
    """Closed polygon of a band of width w along the open polyline `path` (k x 2): one
    side out, the other back. For spokes and other flat bands extruded with `prism`."""
    path = np.asarray(path, float)
    t = np.gradient(path, axis=0)
    t /= np.linalg.norm(t, axis=1)[:, None]
    n = np.c_[-t[:, 1], t[:, 0]]
    return np.r_[path + w/2*n, (path - w/2*n)[::-1]]


def prism(poly, z0, z1):
    """Vertices, faces and tags of the straight prism over the simple polygon `poly` from
    z0 to z1: two n-gon ends ('end') and a quad per edge ('outer')."""
    poly = np.asarray(poly, float)
    k = len(poly)
    verts = np.r_[np.c_[poly, np.full(k, z0)], np.c_[poly, np.full(k, z1)]]
    faces = [tuple(range(k)), tuple(range(2*k - 1, k - 1, -1))]
    faces += [(i, (i + 1) % k, k + (i + 1) % k, k + i) for i in range(k)]
    return verts, faces, ['end', 'end'] + ['outer']*k


# ---------------------------------------------------------------- couplings: simple solids and their assembly
def merge(*parts):
    """One (verts, faces, tags) from several, e.g. a shaft, a plate and two ears of a fork."""
    verts, faces, tags, k = [], [], [], 0
    for v, f, t in parts:
        verts.append(np.asarray(v, float))
        faces += [tuple(i + k for i in face) for face in f]
        tags += list(t)
        k += len(v)
    return np.concatenate(verts), faces, tags


def place(part, R=np.eye(3), t=(0, 0, 0)):
    """The part turned by the matrix R and moved by t: its vertices become R v + t."""
    v, f, tg = part
    return np.asarray(v, float) @ np.asarray(R).T + np.asarray(t, float), f, tg


def cylinder(r, z0, z1, r_in=None, n=96):
    """A cylinder or tube about the z axis from z0 to z1, as (verts, faces, tags)."""
    th = theta_grid(n)
    z = np.array([z0, z1], float)
    r_out = np.full((len(th), 2), float(r))
    r_i = None if r_in is None else np.full((len(th), 2), float(r_in))
    return radial_solid(th, z, r_out, r_i)


def slot(w, L, n=24):
    """Closed polygon of a flat bar w wide with round ends, its end centres at (0, 0) and
    (L, 0): a link, or the ear of a fork with the pin at its centre."""
    a = np.linspace(-np.pi/2, np.pi/2, n)
    right = np.c_[L + w/2*np.cos(a), w/2*np.sin(a)]
    left = np.c_[-w/2*np.cos(a), -w/2*np.sin(a)]
    return np.r_[right, left]


def annular_sector(r0, r1, a0, a1, n=16):
    """Closed polygon of the ring sector r0 <= r <= r1, a0 <= theta <= a1 (radians): a jaw."""
    a = np.linspace(a0, a1, n)
    return np.r_[np.c_[r1*np.cos(a), r1*np.sin(a)], np.c_[r0*np.cos(a[::-1]), r0*np.sin(a[::-1])]]


# axes permutation: a prism built over the (y, z) plane and extruded along x
YZX = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], float)


def fork(d_shaft, L_shaft, a, t, w, c, d_hub=None):
    """The fork (yoke) of a Hooke joint with the pin axis along x through the origin and the
    shaft along -z. Two ears of thickness t and width w stand at |x| = a .. a + t, rounded
    about the pin; they rise from a base plate at z = -c; the shaft of diameter d_shaft
    and length L_shaft continues below a hub of diameter d_hub."""
    d_hub = d_hub or 1.6*d_shaft
    a_ = np.linspace(0, np.pi, 24)                     # the ear in (y, z), round above the pin
    poly = np.r_[[[w/2, -c]], np.c_[w/2*np.cos(a_), w/2*np.sin(a_)], [[-w/2, -c]]]
    parts = [place(prism(poly, x0, x0 + t), YZX) for x0 in (a, -a - t)]
    plate = prism([(-a - t, -w/2), (a + t, -w/2), (a + t, w/2), (-a - t, w/2)], -c - t, -c)
    parts += [plate, cylinder(d_hub/2, -c - t - 0.8*d_shaft, -c - t + 0.1),
              cylinder(d_shaft/2, -c - t - 0.8*d_shaft - L_shaft, -c - t - 0.8*d_shaft + 0.1)]
    return merge(*parts)


def cross(a, t, d_pin, d_body=None):
    """The cross (spider) of a Hooke joint: arms of diameter d_pin along x and y reaching
    through ears at |r| = a .. a + t, on a cube of side d_body at the centre."""
    s = d_body or 1.5*d_pin
    L = a + t + 1.0
    arm_x = place(cylinder(d_pin/2, -L, L), YZX)
    arm_y = place(cylinder(d_pin/2, -L, L), YZX.T)
    body = prism([(-s/2, -s/2), (s/2, -s/2), (s/2, s/2), (-s/2, s/2)], -s/2, s/2)
    return merge(arm_x, arm_y, body)


def spline_bore(N, m, phi_deg=30.0, clearance=0.05):
    """r(theta) of the bore of a hub with an internal involute spline of ISO 4156, flat root,
    that mates with `spline_shaft(N, m)`: its spaces sit where the shaft's teeth are, from the
    minor diameter m(N - 1) to the major diameter m(N + 1.5)."""
    th, r = spur_outline(N, m, phi_deg, n_flank=30, n_land=8, ha=0.75, hf=0.5)
    th, r = np.r_[th - 2*np.pi, th, th + 2*np.pi], np.tile(r, 3) + clearance
    return lambda t: np.interp(np.mod(np.asarray(t, float) + np.pi/N, 2*np.pi) - np.pi/N, th, r)


def spline_shaft(N, m, z0, z1, phi_deg=30.0, n_theta=None):
    """An external involute spline of ISO 4156, 30 degrees, flat root, along z0..z1: N
    teeth of module m between the minor diameter m(N - 1.5) and the major m(N + 1)."""
    th, r = spur_outline(N, m, phi_deg, n_flank=30, n_land=8, ha=0.5, hf=0.75)
    th_c = np.r_[th, th[0] + 2*np.pi]
    r_c = np.r_[r, r[0]]
    z = np.array([z0, z1], float)
    return radial_solid(th_c, z, np.repeat(r_c[:, None], 2, 1))


def spherical_shell(R_in, R_out, z0, z1, a0=0.0, a1=2*np.pi, n_theta=96, n_z=40):
    """The part of a spherical shell R_in <= |x| <= R_out between the planes z0 and z1 (the
    bell of a ball joint), over the angles a0..a1 about z: an open range cuts it open."""
    z = np.linspace(z0, z1, n_z)
    th = np.linspace(a0, a1, n_theta + 1)
    r_out = np.sqrt(np.maximum(R_out**2 - z**2, 0.0)) + 1e-3
    r_in = np.sqrt(np.maximum(R_in**2 - z**2, 0.0)) + 1e-3
    return radial_solid(th, z, np.repeat(r_out[None, :], len(th), 0),
                        np.repeat(r_in[None, :], len(th), 0))


def jaw_hub(d_hub, L_hub, r0, r1, h_jaw, n_jaws=3, jaw_frac=0.5, bore=None):
    """A hub of a jaw coupling: a cylinder of diameter d_hub from z = -L_hub to 0 with
    n_jaws jaws (ring sectors r0..r1, jaw_frac of the pitch wide) standing h_jaw above it;
    the first jaw is centred on +x."""
    w = 2*np.pi/n_jaws*jaw_frac
    parts = [cylinder(d_hub/2, -L_hub, 0.05, r_in=None if bore is None else bore/2)]
    for k in range(n_jaws):
        a = 2*np.pi*k/n_jaws
        parts.append(prism(annular_sector(r0, r1, a - w/2, a + w/2), 0.0, h_jaw))
    return merge(*parts)


def spider(r0, r1, h, n_arms=6, arm_frac=0.5, r_core=None):
    """The elastomer spider between the jaws: n_arms ring sectors r0..r1 joined by a core
    ring, h thick, the first arm centred on +x."""
    w = 2*np.pi/n_arms*arm_frac
    parts = [cylinder(r_core or r0 + 0.25*(r1 - r0), 0.0, h, r_in=r0)]
    for k in range(n_arms):
        a = 2*np.pi*k/n_arms
        parts.append(prism(annular_sector(r0, r1, a - w/2, a + w/2), 0.0, h))
    return merge(*parts)
