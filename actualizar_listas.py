# -*- coding: utf-8 -*-
"""
actualizar_listas.py - Descarga listas publicas de dominios de contenido adulto.

Guarda cada lista como un .txt dentro de /listas, que filtro.py carga
automaticamente. Vuelve a ejecutarlo cuando quieras actualizar.
"""

import os
import sys

try:
    import requests
except ImportError:
    raise SystemExit("Falta 'requests'. Instala con: python -m pip install -r requirements.txt")

BASE = os.path.dirname(os.path.abspath(__file__))
LISTAS_DIR = os.path.join(BASE, "listas")

# Listas publicas de bloqueo de contenido adulto (formato hosts o dominios).
FUENTES = {
    "lista_porno_stevenblack.txt":
        "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/porn/hosts",
    "lista_porno_hagezi.txt":
        "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/adblock/nsfw.txt",
}


def descargar(nombre, url):
    print(f"[..] Descargando {nombre} ...")
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
    except Exception as e:
        print(f"[X ] Error con {nombre}: {e}")
        return 0
    destino = os.path.join(LISTAS_DIR, nombre)
    with open(destino, "w", encoding="utf-8", errors="ignore") as f:
        f.write(r.text)
    lineas = sum(1 for _ in r.text.splitlines())
    print(f"[OK] {nombre}: ~{lineas} lineas guardadas.")
    return lineas


def main():
    os.makedirs(LISTAS_DIR, exist_ok=True)
    total = 0
    for nombre, url in FUENTES.items():
        total += descargar(nombre, url)
    print(f"\n[OK] Listo. ~{total} lineas en total.")
    print("    Reinicia el filtro (o el servicio) para aplicar las listas nuevas.")


if __name__ == "__main__":
    main()
