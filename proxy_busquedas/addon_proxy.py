# -*- coding: utf-8 -*-
"""
addon_proxy.py - Addon de mitmproxy que BLOQUEA busquedas explicitas.

Se carga con:  mitmdump -s addon_proxy.py
(lo hace por ti iniciar_proxy.py).

Que hace:
  - Ve las peticiones a los buscadores (Google, Bing, YouTube, DDG, Yandex...).
  - Lee el TEXTO buscado (parametro q / p / text / search_query...).
  - Se lo pasa al motor (motor_busqueda.Motor). Si es explicito, en vez de
    dejar cargar los resultados devuelve una PAGINA DE BLOQUEO local.
  - Cubre tambien la busqueda de IMAGENES (usa el mismo parametro).

No usa SafeSearch ni guarda tu trafico: solo mira el texto de la busqueda
en TU equipo y decide permitir/bloquear.
"""

import os
import sys
from datetime import datetime

from mitmproxy import http

# Asegura que motor_busqueda.py (misma carpeta) sea importable aunque
# mitmproxy cargue este addon desde otro directorio de trabajo.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from motor_busqueda import Motor

BASE = os.path.dirname(os.path.abspath(__file__))
BLOQUEO_HTML = os.path.join(BASE, "bloqueo.html")
LOG_PATH = os.path.join(BASE, "logs", "busquedas_bloqueadas.log")

# sufijo de host  ->  parametro que lleva el texto buscado
BUSCADORES = {
    "google.": "q",
    "bing.com": "q",
    "duckduckgo.com": "q",
    "search.yahoo.com": "p",
    "yahoo.com": "p",
    "yandex.": "text",
    "search.brave.com": "q",
    "ecosia.org": "q",
    "startpage.com": "query",
    "qwant.com": "q",
    "youtube.com": "search_query",
    "googlevideo.com": "search_query",
}


def _cargar_html():
    try:
        with open(BLOQUEO_HTML, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ("<!doctype html><meta charset='utf-8'>"
                "<h1>Busqueda bloqueada</h1>"
                "<p>Contenido explicito no permitido.</p>")


class FiltroBusquedas:
    def __init__(self):
        self.motor = Motor()
        self.html = _cargar_html()
        print(f"[OK] Filtro de busquedas cargado: "
              f"{len(self.motor.terminos)} terminos, "
              f"{len(self.motor.excepciones)} excepciones.")

    def _param_para(self, host):
        host = (host or "").lower()
        for suf, param in BUSCADORES.items():
            if suf in host:
                return param
        return None

    def _texto_buscado(self, req, param):
        # 1) query string (?q=...)
        try:
            if param in req.query:
                return req.query.get(param)
        except Exception:
            pass
        # 2) formulario POST (application/x-www-form-urlencoded)
        try:
            if param in req.urlencoded_form:
                return req.urlencoded_form.get(param)
        except Exception:
            pass
        return None

    def request(self, flow: http.HTTPFlow):
        req = flow.request
        param = self._param_para(req.pretty_host)
        if not param:
            return
        texto = self._texto_buscado(req, param)
        if not texto:
            return

        bloqueado, motivo = self.motor.evaluar(texto)
        if bloqueado:
            self._registrar(texto, motivo, req.pretty_host)
            cuerpo = self.html.replace("{MOTIVO}", motivo or "").replace(
                "{TEXTO}", (texto[:80] if texto else ""))
            flow.response = http.Response.make(
                200,
                cuerpo.encode("utf-8"),
                {"Content-Type": "text/html; charset=utf-8",
                 "Cache-Control": "no-store"},
            )

    def _registrar(self, texto, motivo, host):
        try:
            os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  BLOQUEADA  "
                        f"[{host}]  '{texto}'  (motivo: {motivo})\n")
        except Exception:
            pass


addons = [FiltroBusquedas()]
