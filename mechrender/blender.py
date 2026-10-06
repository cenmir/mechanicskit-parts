"""Scene, material and render helpers. Runs inside Blender only (needs `bpy`).

The house style is a product shot for a textbook page: a transparent background with a
shadow catcher, so the image works on light and dark pages; Blender's bundled studio HDRI
plus two soft area lights; Cycles with denoising; the camera fitted to the objects.

Geometry is given in millimetres, as in `mechrender.geometry`, and converted to metres
(Blender units) here. Sizes in millimetres keep the numbers the same as on a drawing.
"""
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

MM = 1e-3

# Linear-RGB versions of the book palette (sRGB hex in the comments).
BLUE = (0.035, 0.15, 0.27)      # #236B8E
RED = (0.43, 0.04, 0.03)        # #B03A2E
GOLD = (0.62, 0.38, 0.08)


# ---------------------------------------------------------------- command line
def args():
    """Arguments after Blender's `--`: names, and the flags --preview, --gpu, --out DIR.

    Returns (names, options) where options has keys preview, gpu and out (a Path or None).
    """
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    opts = dict(preview='--preview' in argv, gpu='--gpu' in argv, out=None)
    if '--out' in argv:
        opts['out'] = Path(argv[argv.index('--out') + 1]).resolve()
    skip = {argv.index('--out') + 1} if '--out' in argv else set()
    names = [a for i, a in enumerate(argv) if not a.startswith('--') and i not in skip]
    return names, opts


# ---------------------------------------------------------------- scene
def use_gpu(sc):
    """Render on an NVIDIA card with OptiX, falling back to CUDA.

    read_factory_settings resets the preferences, so this runs after every scene reset.
    """
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for backend in ('OPTIX', 'CUDA'):
        prefs.compute_device_type = backend
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == backend]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == backend
            sc.cycles.device = 'GPU'
            print('Cycles device:', backend, ', '.join(d.name for d in gpus), flush=True)
            return
    raise RuntimeError('--gpu given but no OptiX or CUDA device found')


def reset_scene(preview=False, res=(1600, 1600), samples=128, max_px=1400, gpu=None,
                hdri='studio.exr', hdri_strength=0.35, exposure=-0.6):
    """Start from an empty file and set up Cycles, the film and the world.

    Final images are scaled so the long side is at most `max_px`, the most a page shows.
    A preview renders at 40 % with 32 samples. `gpu=None` follows the --gpu flag.
    """
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    if gpu or (gpu is None and '--gpu' in sys.argv):
        use_gpu(sc)
    sc.cycles.samples = 32 if preview else samples
    sc.cycles.use_denoising = True
    sc.render.film_transparent = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 40 if preview else min(100, int(100*max_px/max(res)))
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.exposure = exposure

    world = bpy.data.worlds.new('World')
    sc.world = world
    if bpy.app.version < (5, 0, 0):
        world.use_nodes = True
    nt = world.node_tree
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    path = Path(bpy.utils.system_resource('DATAFILES')) / 'studiolights' / 'world' / hdri
    env.image = bpy.data.images.load(str(path))
    nt.links.new(env.outputs['Color'], nt.nodes['Background'].inputs['Color'])
    nt.nodes['Background'].inputs['Strength'].default_value = hdri_strength
    return sc


def add_light(loc, energy, size=0.3, target=(0, 0, 0)):
    """An area light at `loc` (metres) aimed at `target`."""
    data = bpy.data.lights.new('Light', 'AREA')
    data.energy, data.size = energy, size
    ob = bpy.data.objects.new('Light', data)
    bpy.context.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return ob


def studio_lights(target, k=1.0):
    """Key light front right and fill light left, scaled by k. Sized for parts of ~5-15 cm."""
    add_light((0.25, -0.3, 0.4), 18*k, 0.3, target=target)
    add_light((-0.35, -0.1, 0.2), 6*k, 0.4, target=target)


def add_camera(loc, target, lens=85, ortho_scale=None):
    """A camera at `loc` looking at `target` (metres), made the scene camera.

    The near clipping plane is 1 mm: Blender's default of 10 cm slices small parts black.
    """
    data = bpy.data.cameras.new('Camera')
    if ortho_scale:
        data.type, data.ortho_scale = 'ORTHO', ortho_scale
    else:
        data.lens = lens
    data.clip_start, data.clip_end = 0.001, 10
    ob = bpy.data.objects.new('Camera', data)
    bpy.context.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = ob
    return ob


def frame(cam, margin=1.2):
    """Slide the camera along its view direction until every mesh fits, plus a margin."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    co = []
    for ob in bpy.context.scene.objects:
        if ob.type == 'MESH' and not ob.is_shadow_catcher:
            ev = ob.evaluated_get(dg)
            co += [c for v in ev.data.vertices for c in ev.matrix_world @ v.co]
    loc, _ = cam.camera_fit_coords(dg, co)
    centre = Vector(np.mean(np.reshape(co, (-1, 3)), axis=0))
    cam.location = centre + (Vector(loc) - centre)*margin
    return cam


def shadow_catcher(z=0.0, size=2.0):
    """An invisible floor that only receives shadows, so the PNG keeps a soft contact shadow."""
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
    ob = bpy.context.object
    ob.is_shadow_catcher = True
    return ob


def render(sc, path):
    """Render the scene camera to `path` (made absolute: Blender reads relative paths
    against the drive root on Windows)."""
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return path


# ---------------------------------------------------------------- materials
def material(name, color, metallic=1.0, roughness=0.28, coat=0.0):
    """A Principled BSDF material. Colours are linear RGB."""
    m = bpy.data.materials.new(name)
    if bpy.app.version < (5, 0, 0):
        m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Roughness'].default_value = roughness
    b.inputs['Coat Weight'].default_value = coat
    return m


def steel(name='Steel', roughness=0.3):
    return bpy.data.materials.get(name) or material(name, (0.62, 0.62, 0.64), roughness=roughness)


def painted(color, name='Paint'):
    """Powder coat: a coloured dielectric under a clear coat."""
    return material(name, color, metallic=0.0, roughness=0.4, coat=0.5)


def dark_plate(name='Plate'):
    return bpy.data.materials.get(name) or material(name, (0.06, 0.065, 0.07), metallic=0.0,
                                                    roughness=0.55)


# ---------------------------------------------------------------- objects from geometry
def wire(name, pts, d, mat, resolution=12):
    """Sweep a circle of diameter d (mm) along the centre line pts (N x 3, mm); returns a mesh."""
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_mode = 'ROUND'
    cu.bevel_depth = d/2*MM
    cu.bevel_resolution = resolution
    cu.use_fill_caps = True
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, np.asarray(pts)*MM):
        p.co = (*q, 1)
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return to_mesh(ob)


def to_mesh(ob):
    """Convert a curve object to a smooth-shaded mesh in place."""
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.ops.object.convert(target='MESH')
    bpy.ops.object.shade_smooth()
    return bpy.context.object


def cut_below_above(ob, z_bot, z_top, size):
    """Remove everything of `ob` below z_bot and above z_top (metres), e.g. grinding.

    Exact booleans are robust but CPU-heavy, the main cost when a scene is rebuilt per frame.
    """
    for zc, sgn in ((z_bot, -1), (z_top, +1)):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, zc + sgn*size))
        cutter = bpy.context.object
        cutter.scale = (3*size, 3*size, 2*size)
        mod = ob.modifiers.new('cut', 'BOOLEAN')
        mod.operation, mod.object, mod.solver = 'DIFFERENCE', cutter, 'EXACT'
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter)
    return ob


def mesh(name, verts, faces, mat, smooth=False, bevel=None):
    """A mesh object from vertex (mm) and face arrays, e.g. from geometry.revolve."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in np.asarray(verts)*MM], [], faces)
    me.validate()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    if bevel:
        bev = ob.modifiers.new('bevel', 'BEVEL')
        bev.width, bev.segments, bev.limit_method = bevel*MM, 2, 'ANGLE'
    ob.data.materials.append(mat)
    for f in me.polygons:
        f.use_smooth = smooth
    return ob


def box(name, size, z, mat, location=(0, 0), bevel=0.6):
    """A bevelled box of size (x, y, thickness) mm whose bottom face is at height z (mm)."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=(location[0]*MM, location[1]*MM,
                                                      (z + size[2]/2)*MM))
    ob = bpy.context.object
    ob.name = name
    ob.scale = tuple(s*MM for s in size)
    bev = ob.modifiers.new('bevel', 'BEVEL')
    bev.width, bev.segments = bevel*MM, 3
    ob.data.materials.append(mat)
    return ob
