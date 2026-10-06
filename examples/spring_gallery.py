"""A first mechanicskit-parts scene: three spring types side by side.

    blender -b -P examples/spring_gallery.py -- [--preview] [--gpu] [--out DIR]
    bin/remote-render examples/spring_gallery.py              # on the GPU machine

Writes spring_gallery.png into --out (default: ./out).
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The package sits next to this file on the render machine, one level up in the repo.
sys.path[:0] = [str(HERE), str(HERE.parent), os.environ.get('MKPARTS', '')]

from mkparts import blender as mb  # noqa: E402
from mkparts.blender import BLUE, RED  # noqa: E402
from mkparts.springs import compression_spring, disc_spring, torsion_spring  # noqa: E402

names, opts = mb.args()
sc = mb.reset_scene(opts['preview'], res=(2400, 1200))

# A compression spring with closed and ground ends: D = 24 mm, d = 3 mm, 6 active coils.
compression_spring('Compression', D=24, d=3.0, n_active=6, p=8, mat=mb.painted(BLUE),
                   location=(-52, 0, 0))
# A close-wound torsion spring; its two straight legs leave the coil at right angles.
torsion_spring('Torsion', D=16, d=2.0, n=5, leg=26, mat=mb.painted(RED), location=(0, 0, 1))
# Four disc springs, alternately flipped: a series stack.
for i in range(4):
    disc_spring(f'Disc{i}', De=30, Di=15.3, t=1.2, h0=1.6, mat=mb.steel(),
                location=(40, 0, i*1.2 if i % 2 else 1.6 + i*1.2), flip=bool(i % 2))

mb.shadow_catcher(size=3)
mb.studio_lights((0, 0, 0.02))
mb.frame(mb.add_camera((0.0, -0.5, 0.2), (0, 0, 0.02), lens=55))
mb.render(sc, (opts['out'] or Path('out')) / 'spring_gallery.png')
