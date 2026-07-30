# -*- coding: utf-8 -*-
"""
iniciar_proxy.py - Arranca el proxy de filtrado de busquedas (mitmdump).

Lee la config compartida (config.json del proyecto) para saber el puerto y
si la capa esta activada, localiza el ejecutable mitmdump y lo lanza con
nuestro addon (addon_proxy.py).

Lo mantiene vivo el vigilante_proxy.py (igual que vigilante.py con el DNS).
"""

import json
import os
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.join(BASE, "addon_proxy.py")
# Carpeta FIJA del certificado (CA). Debe ser la misma que usa el instalador
# al generar/instalar el CA, para que el proxy (corriendo como SYSTEM) use ese
# mismo certificado y el navegador no de errores de seguridad.
CONFDIR = os.path.join(BASE, "mitmproxy")

# config.json vive en la raiz del proyecto (una carpeta arriba del modulo).
CONFIG_CANDIDATOS = [
    os.path.join(os.path.dirname(BASE), "config.json"),
    os.path.join(BASE, "config.json"),
]

DEFAULTS = {"enabled": True, "puerto": 8080, "listen_host": "127.0.0.1"}

# Solo se INSPECCIONA el HTTPS de los buscadores; todo lo demas (winget, banca,
# Windows Update, googlevideo/YouTube playback, apps con pinning...) pasa SIN
# interceptar. Usamos --allow-hosts (opcion inversa de mitmproxy): intercepta
# SOLO los hosts que coincidan con este regex; el resto se tunela sin tocar.
ALLOW_HOSTS = (
    r"(google\.|bing\.com|duckduckgo\.com|search\.yahoo|yahoo\.com|yandex\.|"
    r"search\.brave|ecosia\.org|startpage\.com|qwant\.com|youtube\.com)"
)


def cargar_config():
    for ruta in CONFIG_CANDIDATOS:
        if os.path.exists(ruta):
            try:
                with open(ruta, "r", encoding="utf-8-sig") as f:  # tolera BOM
                    cfg = json.load(f)
                return cfg.get("proxy_busquedas", {}) or {}
            except Exception:
                pass
    return {}


def localizar_mitmdump():
    # 1) en el PATH
    ruta = shutil.which("mitmdump")
    if ruta:
        return ruta
    # 2) junto al python actual (…\Scripts\mitmdump.exe)
    scripts = os.path.join(os.path.dirname(sys.executable), "Scripts")
    for nombre in ("mitmdump.exe", "mitmdump"):
        cand = os.path.join(scripts, nombre)
        if os.path.exists(cand):
            return cand
    return None


def main():
    cfg = {**DEFAULTS, **cargar_config()}
    if not cfg.get("enabled", True):
        print("[i] proxy_busquedas.enabled = false -> no se arranca.")
        return 0

    mitmdump = localizar_mitmdump()
    if not mitmdump:
        print("[X] No se encontro 'mitmdump'. Instala con: "
              "python -m pip install mitmproxy")
        return 2

    os.makedirs(CONFDIR, exist_ok=True)
    cmd = [
        mitmdump,
        "--listen-host", str(cfg["listen_host"]),
        "-p", str(cfg["puerto"]),
        "-s", ADDON,
        "-q",                      # silencioso (solo nuestros prints/log)
        "--set", "flow_detail=0",
        "--set", f"confdir={CONFDIR}",
        "--allow-hosts", ALLOW_HOSTS,   # interceptar SOLO los buscadores
    ]
    print(f"[OK] Iniciando proxy de busquedas en "
          f"{cfg['listen_host']}:{cfg['puerto']}  (mitmdump)")
    # cwd=BASE para que el addon resuelva rutas relativas.
    proc = subprocess.run(cmd, cwd=BASE)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
