# -*- coding: utf-8 -*-
"""
generar_icono.py - Genera los recursos graficos del instalador (Pillow):
  - icono.ico       : icono del .exe y de la ventana (escudo azul + check)
  - escudo_hero.png : escudo grande para la pantalla de bienvenida
  - paypal.png      : icono minimalista de PayPal (doble P) para el boton donar
"""
import os
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
SS = 4  # supersampling para bordes suaves

TOP = (61, 139, 255)   # azul claro (arriba del degradado)
BOT = (22, 82, 194)    # azul profundo (abajo)


def _shield(final_w, final_h):
    W, H = final_w * SS, final_h * SS
    k = W / 240.0

    def P(pts):
        return [(x * k, y * k) for (x, y) in pts]

    shield = P([(40, 40), (200, 40), (200, 116), (190, 150),
                (160, 192), (120, 232), (80, 192), (60, 150), (40, 116)])

    grad = Image.new("RGB", (W, H))
    gd = ImageDraw.Draw(grad)
    for y in range(H):
        t = y / max(1, H - 1)
        gd.line([(0, y), (W, y)],
                fill=(int(TOP[0] + (BOT[0] - TOP[0]) * t),
                      int(TOP[1] + (BOT[1] - TOP[1]) * t),
                      int(TOP[2] + (BOT[2] - TOP[2]) * t)))

    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon(shield, fill=255)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)
    d.line(shield + [shield[0]], fill=(130, 185, 255, 180), width=int(3 * k), joint="curve")
    check = P([(90, 134), (114, 160), (162, 98)])
    d.line(check, fill=(245, 250, 255, 255), width=int(16 * k), joint="curve")
    for (x, y) in (check[0], check[-1]):
        r = int(8 * k)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(245, 250, 255, 255))
    return img.resize((final_w, final_h), Image.LANCZOS)


def _paypal(size):
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", int(S * 0.9))
    except Exception:
        font = ImageFont.load_default()
    dark = (0, 48, 135, 255)     # PayPal azul oscuro
    light = (0, 156, 222, 255)   # PayPal azul claro
    d.text((S * 0.58, S * 0.52), "P", font=font, fill=dark, anchor="mm")
    d.text((S * 0.42, S * 0.46), "P", font=font, fill=light, anchor="mm")
    return img.resize((size, size), Image.LANCZOS)


# HERO
_shield(230, 250).save(os.path.join(BASE, "escudo_hero.png"))

# ICONO (centrado en lienzo cuadrado)
canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
sh = _shield(220, 238)
canvas.paste(sh, ((256 - 220) // 2, (256 - 238) // 2), sh)
canvas.save(os.path.join(BASE, "icono.ico"), format="ICO",
            sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])

# PAYPAL
_paypal(44).save(os.path.join(BASE, "paypal.png"))

print("OK: escudo_hero.png, icono.ico, paypal.png")
