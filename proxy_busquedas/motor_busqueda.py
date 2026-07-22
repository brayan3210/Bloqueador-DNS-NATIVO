# -*- coding: utf-8 -*-
"""
motor_busqueda.py - "Cerebro" compartido del bloqueo por PALABRA DE BUSQUEDA.

A diferencia de filtro.py (el filtro DNS, que mira DOMINIOS), esto mira el
TEXTO que escribes en el buscador (Google, Bing, YouTube, etc.). Lo usa el
proxy del PC (addon_proxy.py). La MISMA logica se replicara en la app Android
con el servicio de accesibilidad.

No usa el SafeSearch de Google.

Reglas de decision:
  1. Se BLOQUEA si el texto contiene algun termino EXPLICITO del catalogo
     (listas/catalogo_busqueda.txt).
  2. Las palabras anatomicas/educativas (pene, vagina, utero, ...) van en
     listas/excepciones_educativas.txt y NO bloquean por si solas: se restan
     del catalogo al cargar. Solo se bloquea si en el mismo texto ADEMAS
     aparece un termino explicito (ej.: "vagina xxx" -> bloquea por "xxx";
     "vagina anatomia" -> permite).
  3. Terminos de UNA palabra: coincidencia por INICIO de palabra, de modo que
     "porn" atrapa "porn/porno/pornografia" pero NO "essex" (por "sex").
     Terminos con ESPACIOS (ej.: "nasty ass"): coincidencia por subcadena.
"""

import os
import re
import unicodedata

BASE = os.path.dirname(os.path.abspath(__file__))
LISTAS_DIR = os.path.join(BASE, "listas")
CAT_PATH = os.path.join(LISTAS_DIR, "catalogo_busqueda.txt")
EXC_PATH = os.path.join(LISTAS_DIR, "excepciones_educativas.txt")


def normalizar(texto):
    """minusculas + sin acentos + solo [a-z0-9 espacio]."""
    if not texto:
        return ""
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _cargar_lista(ruta):
    palabras = []
    if not os.path.exists(ruta):
        return palabras
    with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            n = normalizar(ln)
            if n:
                palabras.append(n)
    return palabras


class Motor:
    def __init__(self):
        self.recargar()

    def recargar(self):
        catalogo = _cargar_lista(CAT_PATH)
        self.excepciones = set(_cargar_lista(EXC_PATH))

        # Garantia dura: una palabra de excepcion NUNCA queda en el catalogo,
        # asi jamas bloquea sola (aunque por error se agregue al catalogo).
        terminos = []
        vistos = set()
        for t in catalogo:
            if t in self.excepciones:
                continue
            if t in vistos:
                continue
            vistos.add(t)
            terminos.append(t)
        self.terminos = terminos

        self._multiword = [t for t in terminos if " " in t]
        self._single = [t for t in terminos if " " not in t]
        self._regex = None
        if self._single:
            patron = r"\b(" + "|".join(re.escape(t) for t in self._single) + r")"
            self._regex = re.compile(patron)

    def evaluar(self, texto):
        """Devuelve (bloqueado: bool, motivo: str|None)."""
        q = normalizar(texto)
        if not q:
            return (False, None)
        for t in self._multiword:
            if t in q:
                return (True, t)
        if self._regex is not None:
            m = self._regex.search(q)
            if m:
                return (True, m.group(1))
        return (False, None)


# --------------------------------------------------------------------------
# Autoprueba:  python motor_busqueda.py
# --------------------------------------------------------------------------
def _selftest():
    m = Motor()
    print(f"[i] Catalogo: {len(m.terminos)} terminos activos "
          f"({len(m._multiword)} frases, {len(m._single)} palabras). "
          f"Excepciones: {len(m.excepciones)}.")
    casos = [
        ("porn", True),
        ("videos porno gratis", True),
        ("chubby girls", True),
        ("nasty ass", True),
        ("xvideos", True),
        ("vagina xxx", True),                    # explicito co-ocurre -> bloquea
        ("pene anatomia humana", False),         # educativo -> permite
        ("aparato reproductor femenino", False),
        ("vagina biologia celular", False),
        ("menstruacion ciclo", False),
        ("noticias bbc en vivo", False),         # bbc NO esta en catalogo
        ("essex england turismo", False),        # 'sex' dentro de essex: NO bloquea
        ("analisis de datos", False),            # 'anal' dentro de analisis: NO bloquea
        ("clima manana bogota", False),
    ]
    ok = 0
    for texto, esperado in casos:
        b, motivo = m.evaluar(texto)
        estado = "OK  " if b == esperado else "FALLA"
        if b == esperado:
            ok += 1
        print(f"[{estado}] '{texto}' -> bloqueado={b} motivo={motivo!r}")
    print(f"\n{ok}/{len(casos)} casos correctos.")
    return ok == len(casos)


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
