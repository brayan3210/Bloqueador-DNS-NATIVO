# -*- coding: utf-8 -*-
"""
vigilante_proxy.py - Mantiene VIVO y SANO el proxy de filtrado de busquedas.

MEJORA CLAVE (v2): no basta con que el proceso exista. Se comprueba que el proxy
REALMENTE escuche en su puerto. Un mitmdump "colgado" (proceso vivo pero sin
aceptar conexiones) dejaba el proxy del sistema apuntando a un puerto muerto, y
el equipo se quedaba SIN INTERNET (todo el navegador iba a un proxy caido).

Ahora:
  * Health-check por TCP al puerto: si no responde, se mata mitmdump y se relanza.
  * Fail-safe: si tras varios intentos el proxy sigue sin escuchar, se DESACTIVA
    el proxy del sistema del usuario para que NUNCA se quede sin internet (el
    filtro DNS sigue protegiendo). Se reactiva solo cuando el proxy vuelve.

Sale limpio si encuentra la senal .parar_proxy (la crea desactivar_proxy.ps1 tras
validar la contrasena). No es un rootkit: como eres administrador siempre puedes
detenerlo con la contrasena.
"""

import json
import os
import socket
import subprocess
import sys
import time
import winreg

BASE = os.path.dirname(os.path.abspath(__file__))
INICIAR = os.path.join(BASE, "iniciar_proxy.py")
SENAL_PARAR = os.path.join(BASE, ".parar_proxy")
LOG_DIR = os.path.join(BASE, "logs")
LOG = os.path.join(LOG_DIR, "vigilante_proxy.log")

# config.json vive en la raiz del proyecto (una carpeta arriba del modulo).
CONFIG_CANDIDATOS = [
    os.path.join(os.path.dirname(BASE), "config.json"),
    os.path.join(BASE, "config.json"),
]

HOST = "127.0.0.1"
FAILS_PARA_FAILOPEN = 3     # ciclos fallidos antes de liberar el internet
ESPERA_BIND_S = 12          # segundos a esperar a que mitmdump abra el puerto


def log(msg):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def leer_puerto():
    for ruta in CONFIG_CANDIDATOS:
        if os.path.exists(ruta):
            try:
                with open(ruta, "r", encoding="utf-8-sig") as f:  # tolera BOM
                    cfg = json.load(f)
                pb = cfg.get("proxy_busquedas", {}) or {}
                return int(pb.get("puerto", 8080))
            except Exception:
                pass
    return 8080


def escuchando(port):
    """True si algo acepta conexiones TCP en HOST:port (proxy realmente vivo)."""
    try:
        with socket.create_connection((HOST, port), timeout=1.5):
            return True
    except OSError:
        return False


def matar_mitmdump():
    try:
        subprocess.run(["taskkill", "/F", "/IM", "mitmdump.exe"],
                       capture_output=True, timeout=15)
    except Exception:
        pass


def lanzar():
    # iniciar_proxy.py bloquea mientras mitmdump vive (lo lanza con subprocess.run).
    return subprocess.Popen([sys.executable, INICIAR])


def set_proxy_usuario(enabled):
    """Activa/desactiva el proxy del sistema en los hives de usuario que tengan
    configurado NUESTRO proxy (127.0.0.1:*). Corremos como SYSTEM, por eso hay que
    escribir en HKEY_USERS\\<SID> (HKCU seria el hive de SYSTEM, no el del usuario)."""
    tocados = 0
    try:
        i = 0
        while True:
            try:
                sid = winreg.EnumKey(winreg.HKEY_USERS, i)
                i += 1
            except OSError:
                break
            if not sid.startswith("S-1-5-21") or sid.endswith("_Classes"):
                continue
            sub = sid + r"\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
            try:
                k = winreg.OpenKey(winreg.HKEY_USERS, sub, 0,
                                   winreg.KEY_READ | winreg.KEY_WRITE)
            except OSError:
                continue
            try:
                server = str(winreg.QueryValueEx(k, "ProxyServer")[0])
            except OSError:
                server = ""
            if "127.0.0.1:" in server:
                winreg.SetValueEx(k, "ProxyEnable", 0, winreg.REG_DWORD,
                                  1 if enabled else 0)
                tocados += 1
            winreg.CloseKey(k)
    except Exception as e:
        log(f"set_proxy_usuario error: {e}")
    return tocados


def main():
    port = leer_puerto()
    log(f"Vigilante del proxy activo (puerto {port}).")
    proc = None
    fails = 0
    proxy_liberado = False   # True si NOSOTROS desactivamos el proxy (fail-open)

    while True:
        if os.path.exists(SENAL_PARAR):
            log("Senal de parada (desactivacion autorizada). Saliendo.")
            matar_mitmdump()
            if proc and proc.poll() is None:
                try: proc.terminate()
                except Exception: pass
            try: os.remove(SENAL_PARAR)
            except Exception: pass
            break

        if escuchando(port):
            if fails or proxy_liberado:
                log("Proxy sano de nuevo.")
            fails = 0
            if proxy_liberado:
                set_proxy_usuario(True)
                proxy_liberado = False
                log("Proxy del sistema RE-ACTIVADO (internet + filtro de busquedas).")
            time.sleep(5)
            continue

        # No escucha: mitmdump muerto o COLGADO -> forzar reinicio limpio.
        log("Proxy NO responde. Reiniciando mitmdump...")
        matar_mitmdump()
        if proc and proc.poll() is None:
            try: proc.terminate()
            except Exception: pass
        proc = lanzar()

        bound = False
        for _ in range(ESPERA_BIND_S):
            time.sleep(1)
            if escuchando(port):
                bound = True
                break

        if bound:
            fails = 0
            log("mitmdump escuchando de nuevo.")
            if proxy_liberado:
                set_proxy_usuario(True)
                proxy_liberado = False
                log("Proxy del sistema RE-ACTIVADO.")
        else:
            fails += 1
            log(f"mitmdump sigue sin escuchar (fallo {fails}).")
            if fails >= FAILS_PARA_FAILOPEN and not proxy_liberado:
                n = set_proxy_usuario(False)
                proxy_liberado = True
                log(f"FAIL-OPEN: proxy del sistema DESACTIVADO en {n} usuario(s) "
                    f"para no dejar sin internet. El filtro DNS sigue activo.")
        time.sleep(3)


if __name__ == "__main__":
    main()
