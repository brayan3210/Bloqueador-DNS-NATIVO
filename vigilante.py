# -*- coding: utf-8 -*-
"""
vigilante.py - Mantiene VIVO y SANO el filtro DNS.

MEJORA (v2): ademas de relanzar filtro.py si el proceso muere, ahora comprueba
que el DNS RESPONDA de verdad en 127.0.0.1:53. Si filtro.py se cuelga (proceso
vivo pero sin atender consultas), tambien se reinicia. Antes, un proceso zombi
dejaba el equipo sin resolucion DNS (y sin internet) para siempre.

El "latido" consulta un dominio que el propio filtro BLOQUEA (responde 0.0.0.0
localmente): asi la comprobacion NO depende de que haya internet, solo de que el
filtro este vivo y atendiendo. Es tolerante (varios fallos seguidos) para no
reiniciar por un hipo puntual.

Esto NO es un rootkit: es solo un relanzador con chequeo de salud. Como eres
administrador siempre podras detenerlo con la contrasena via desinstalar.ps1.
"""

import os
import socket
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
FILTRO = os.path.join(BASE, "filtro.py")
SENAL_PARAR = os.path.join(BASE, ".parar")   # se crea al desinstalar con contrasena
LOG_DIR = os.path.join(BASE, "logs")
LOG = os.path.join(LOG_DIR, "vigilante.log")

HOST = "127.0.0.1"
# Dominio-sonda que el filtro bloquea localmente (respuesta instantanea, sin
# necesitar internet). Solo se usa para comprobar que el filtro responde.
SONDA = "pornhub.com"
FALLOS_PARA_REINICIO = 6      # ~35s sin responder = colgado de verdad


def log(msg):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _consulta(nombre):
    """Arma una consulta DNS tipo A minima para 'nombre'."""
    q = bytes([0x12, 0x34, 0x01, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    for parte in nombre.encode("ascii").split(b"."):
        q += bytes([len(parte)]) + parte
    q += b"\x00" + bytes([0x00, 0x01, 0x00, 0x01])
    return q


def dns_responde(port=53):
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2.0)
        s.sendto(_consulta(SONDA), (HOST, port))
        data, _ = s.recvfrom(512)
        return len(data) >= 2 and data[0] == 0x12 and data[1] == 0x34
    except Exception:
        return False
    finally:
        if s:
            try: s.close()
            except Exception: pass


def lanzar_filtro():
    return subprocess.Popen([sys.executable, FILTRO])


def reiniciar(proc):
    try:
        if proc and proc.poll() is None:
            proc.terminate()
    except Exception:
        pass
    try:
        if proc:
            subprocess.run(["taskkill", "/F", "/PID", str(proc.pid)],
                           capture_output=True, timeout=10)
    except Exception:
        pass
    time.sleep(2)   # dar tiempo a liberar el socket 53 antes de rebindear
    return lanzar_filtro()


def main():
    log("Vigilante DNS activo (con chequeo de salud).")
    proc = None
    fallos = 0
    while True:
        if os.path.exists(SENAL_PARAR):
            log("Senal de parada (desinstalacion autorizada). Saliendo.")
            if proc and proc.poll() is None:
                try: proc.terminate()
                except Exception: pass
            try: os.remove(SENAL_PARAR)
            except Exception: pass
            break

        if proc is None or proc.poll() is not None:
            log("Filtro caido. Relanzando...")
            proc = lanzar_filtro()
            fallos = 0
            time.sleep(3)
            continue

        # Proceso vivo: comprobar que ademas RESPONDA.
        if dns_responde():
            fallos = 0
        else:
            fallos += 1
            if fallos >= FALLOS_PARA_REINICIO:
                log("Filtro vivo pero NO responde (colgado). Reiniciando...")
                proc = reiniciar(proc)
                fallos = 0

        time.sleep(5)


if __name__ == "__main__":
    main()
