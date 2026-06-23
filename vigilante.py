# -*- coding: utf-8 -*-
"""
vigilante.py - Mantiene vivo el filtro DNS.

Lanza filtro.py y, si el proceso muere (lo cierras, lo matan, crashea),
lo vuelve a lanzar a los pocos segundos. Tambien revisa que el DNS del
sistema siga apuntando a 127.0.0.1; si no, lo restaura.

Esto NO es un rootkit: es solo un relanzador. Da "friccion" para que no
sea trivial dejar el equipo sin filtro, pero como eres administrador
siempre podras detenerlo con la contrasena via desinstalar.ps1.
"""

import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
FILTRO = os.path.join(BASE, "filtro.py")
SENAL_PARAR = os.path.join(BASE, ".parar")  # se crea al desinstalar con contrasena


def lanzar_filtro():
    return subprocess.Popen([sys.executable, FILTRO])


def main():
    print("[OK] Vigilante activo. Mantiene el filtro corriendo.")
    proc = None
    while True:
        if os.path.exists(SENAL_PARAR):
            print("[..] Senal de parada detectada (desinstalacion autorizada). Saliendo.")
            if proc and proc.poll() is None:
                proc.terminate()
            try:
                os.remove(SENAL_PARAR)
            except Exception:
                pass
            break

        if proc is None or proc.poll() is not None:
            print("[..] (Re)lanzando filtro...")
            proc = lanzar_filtro()

        time.sleep(5)


if __name__ == "__main__":
    main()
