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
