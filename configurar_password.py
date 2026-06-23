# -*- coding: utf-8 -*-
"""
configurar_password.py - Define la contrasena necesaria para desactivar el filtro.

CONSEJO (autocontrol): para que de verdad funcione contra el impulso,
pidele a una persona de confianza que escriba ELLA la contrasena aqui y
NO te la diga. Asi no podras desactivarlo solo en un momento de debilidad.
"""

import getpass
import hashlib
import json
import os
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "config.json")
EXAMPLE_PATH = os.path.join(BASE, "config.example.json")


def main():
    # Si no existe config.json (primera vez tras clonar), crearlo desde la plantilla.
    if not os.path.exists(CONFIG_PATH) and os.path.exists(EXAMPLE_PATH):
        shutil.copy(EXAMPLE_PATH, CONFIG_PATH)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    p1 = getpass.getpass("Nueva contrasena para desactivar el filtro: ")
    p2 = getpass.getpass("Repite la contrasena: ")
    if p1 != p2:
        print("[X] No coinciden. No se cambio nada.")
        return
    if len(p1) < 4:
        print("[X] Demasiado corta.")
        return

    config["password_hash"] = hashlib.sha256(p1.encode("utf-8")).hexdigest()
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print("[OK] Contrasena guardada.")


if __name__ == "__main__":
    main()
