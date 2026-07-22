# -*- coding: utf-8 -*-
"""
vigilante_proxy.py - Mantiene vivo el proxy de filtrado de busquedas.

Lanza iniciar_proxy.py y, si el proceso muere, lo relanza a los pocos
segundos. Sale limpio si encuentra la senal .parar_proxy (la crea
desactivar_proxy.ps1 tras validar la contrasena).

Es un simple relanzador (da friccion), no un rootkit: como eres
administrador siempre puedes detenerlo con la contrasena.
"""

import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
INICIAR = os.path.join(BASE, "iniciar_proxy.py")
SENAL_PARAR = os.path.join(BASE, ".parar_proxy")


def lanzar():
    return subprocess.Popen([sys.executable, INICIAR])


def main():
    print("[OK] Vigilante del proxy de busquedas activo.")
    proc = None
    while True:
        if os.path.exists(SENAL_PARAR):
            print("[..] Senal de parada detectada (desactivacion autorizada). Saliendo.")
            if proc and proc.poll() is None:
                proc.terminate()
            try:
                os.remove(SENAL_PARAR)
            except Exception:
                pass
            break

        if proc is None or proc.poll() is not None:
            print("[..] (Re)lanzando proxy de busquedas...")
            proc = lanzar()

        time.sleep(5)


if __name__ == "__main__":
    main()
