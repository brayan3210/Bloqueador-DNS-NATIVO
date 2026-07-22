# -*- coding: utf-8 -*-
"""
generar_icono.py - Crea icono.ico (escudo + cerradura, navy+oro) para el .exe.
Se renderiza a 4x y se reduce para bordes suaves. Requiere Pillow.
"""
import os
from PIL import Image, ImageDraw

S = 1024                      # lienzo grande (antialias por reduccion)
NAVY = (18, 28, 49, 255)      # #121c31
NAVY_D = (8, 14, 26, 255)     # borde interno oscuro
GOLD = (230, 185, 85, 255)    # #e6b955

img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

k = S / 256.0
def P(pts): return [(x * k, y * k) for (x, y) in pts]

# Escudo (pentagono con punta abajo)
shield = P([(46, 50), (210, 50), (210, 132), (128, 224), (46, 132)])

# Sombra sutil
d.polygon([(x, y + 8 * k) for (x, y) in shield], fill=(0, 0, 0, 60))
# Cuerpo navy
d.polygon(shield, fill=NAVY)
# Borde dorado (linea gruesa)
d.line(shield + [shield[0]], fill=GOLD, width=int(11 * k), joint="curve")

# Cerradura (circulo + trapecio) en oro
cx, cy, r = 128 * k, 104 * k, 26 * k
d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GOLD)
d.polygon(P([(114, 118), (142, 118), (150, 176), (106, 176)]), fill=GOLD)
# Agujero interior de la cerradura (navy) para dar forma
hr = 11 * k
d.ellipse([cx - hr, cy - hr, cx + hr, cy + hr], fill=NAVY)

# Reducir a 256 y exportar multi-size
base = img.resize((256, 256), Image.LANCZOS)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icono.ico")
base.save(out, format="ICO",
          sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print("OK ->", out, os.path.getsize(out), "bytes")
