# -*- coding: utf-8 -*-
"""
filtro.py - Servidor DNS local de filtrado de contenido.

Funcionamiento:
  - Escucha consultas DNS en 127.0.0.1:53 (tu PC apunta su DNS aqui).
  - Para cada dominio consultado decide:
        * BLOQUEAR  -> responde 0.0.0.0 (la conexion no se puede hacer).
        * PERMITIR  -> reenvia la consulta al DNS de internet (upstream).
  - Se bloquea si:
        * el dominio (o un dominio padre) esta en alguna lista de dominios,
        * el dominio CONTIENE alguna palabra clave que tu definas,
        * la IP que devuelve el upstream esta en tu lista de IPs bloqueadas.

No usa SafeSearch de Google ni descifra trafico: bloquea destinos por DNS.
"""

import json
import os
import socket
import socketserver
import threading
import time
from datetime import datetime

try:
    from dnslib import DNSRecord, RR, A, AAAA, QTYPE, RCODE
except ImportError:
    raise SystemExit(
        "Falta la libreria 'dnslib'. Instalala con:\n"
        "    python -m pip install -r requirements.txt"
    )

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "config.json")
LISTAS_DIR = os.path.join(BASE, "listas")
LOG_PATH = os.path.join(BASE, "logs", "bloqueados.log")


# --------------------------------------------------------------------------
# Carga de configuracion y listas
# --------------------------------------------------------------------------
def cargar_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _parsear_linea_dominio(linea):
    """Acepta formato 'hosts' (0.0.0.0 dominio) o solo el dominio."""
    linea = linea.strip()
    if not linea or linea.startswith("#"):
        return None
    partes = linea.split()
    # formato hosts: "0.0.0.0 ejemplo.com"  o  "127.0.0.1 ejemplo.com"
    if len(partes) >= 2 and (partes[0] in ("0.0.0.0", "127.0.0.1", "::1")):
        dom = partes[1]
    else:
        dom = partes[0]
    dom = dom.lower().strip(".")
    if dom in ("localhost", "localhost.localdomain", "broadcasthost"):
        return None
    return dom or None


def cargar_listas():
    """Devuelve (set_dominios, lista_palabras, set_ips)."""
    dominios = set()
    palabras = []
    ips = set()

    # Todos los .txt dentro de /listas se tratan como listas de DOMINIOS,
    # excepto los archivos especiales de palabras e IPs.
    especiales = {"palabras_clave.txt", "ips_bloqueadas.txt"}

    for nombre in os.listdir(LISTAS_DIR):
        if not nombre.lower().endswith(".txt"):
            continue
        ruta = os.path.join(LISTAS_DIR, nombre)

        if nombre == "palabras_clave.txt":
            with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
                for ln in f:
                    ln = ln.strip().lower()
                    if ln and not ln.startswith("#"):
                        palabras.append(ln)
            continue

        if nombre == "ips_bloqueadas.txt":
            with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
                for ln in f:
                    ln = ln.strip()
                    if ln and not ln.startswith("#"):
                        ips.add(ln)
            continue

        if nombre in especiales:
            continue

        with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
            for ln in f:
                dom = _parsear_linea_dominio(ln)
                if dom:
                    dominios.add(dom)

    return dominios, palabras, ips


# --------------------------------------------------------------------------
# Logica de decision
# --------------------------------------------------------------------------
class Filtro:
    def __init__(self, config):
        self.config = config
        self.dominios, self.palabras, self.ips = cargar_listas()
        self.lock = threading.Lock()
        print(f"[OK] Listas cargadas: {len(self.dominios)} dominios, "
              f"{len(self.palabras)} palabras clave, {len(self.ips)} IPs.")

    def recargar(self):
        with self.lock:
            self.dominios, self.palabras, self.ips = cargar_listas()
        print(f"[OK] Listas RECARGADAS: {len(self.dominios)} dominios, "
              f"{len(self.palabras)} palabras, {len(self.ips)} IPs.")

    def dominio_bloqueado(self, qname):
        qname = qname.lower().strip(".")
        with self.lock:
            # 1) coincidencia exacta o de dominio padre
            labels = qname.split(".")
            for i in range(len(labels) - 1):
                if ".".join(labels[i:]) in self.dominios:
                    return "lista"
            if qname in self.dominios:
                return "lista"
            # 2) palabra clave dentro del dominio
            for palabra in self.palabras:
                if palabra in qname:
                    return f"palabra '{palabra}'"
        return None

    def ip_bloqueada(self, ip):
        with self.lock:
            return ip in self.ips


# --------------------------------------------------------------------------
# Servidor DNS
# --------------------------------------------------------------------------
def registrar_bloqueo(dominio, motivo):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  BLOQUEADO  {dominio}  ({motivo})\n")
    except Exception:
        pass


def reenviar_upstream(data, upstreams, puerto, timeout=3, intentos=2):
    """Reenvia la consulta probando varios DNS upstream con reintentos.
    upstreams: lista de IPs (se prueban en orden). Asi no se pierde ninguna
    consulta por un timeout puntual."""
    ultimo_error = None
    for ip in upstreams:
        for _ in range(intentos):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(timeout)
            try:
                s.sendto(data, (ip, puerto))
                respuesta, _ = s.recvfrom(4096)
                return respuesta
            except Exception as e:
                ultimo_error = e
            finally:
                s.close()
    raise (ultimo_error or TimeoutError("upstream sin respuesta"))


def construir_respuesta_bloqueo(request, block_ip):
    reply = request.reply()
    qtype = QTYPE[request.q.qtype]
    if qtype == "A":
        reply.add_answer(RR(request.q.qname, QTYPE.A, rdata=A(block_ip), ttl=60))
    elif qtype == "AAAA":
        reply.add_answer(RR(request.q.qname, QTYPE.AAAA, rdata=AAAA("::"), ttl=60))
    else:
        reply.header.rcode = RCODE.NXDOMAIN
    return reply.pack()


def hacer_handler(filtro):
    cfg = filtro.config
    upstreams = [cfg["upstream"]]
    if cfg.get("upstream2"):
        upstreams.append(cfg["upstream2"])
    upstream_port = cfg.get("upstream_port", 53)
    block_ip = cfg.get("block_response", "0.0.0.0")
    log_blocked = cfg.get("log_blocked", True)

    class DNSHandler(socketserver.BaseRequestHandler):
        def handle(self):
            data, sock = self.request
            try:
                request = DNSRecord.parse(data)
            except Exception:
                return
            qname = str(request.q.qname).rstrip(".")

            motivo = filtro.dominio_bloqueado(qname)
            if motivo:
                if log_blocked:
                    registrar_bloqueo(qname, motivo)
                sock.sendto(construir_respuesta_bloqueo(request, block_ip),
                            self.client_address)
                return

            # Permitido: reenviar al DNS de internet
            try:
                respuesta = reenviar_upstream(data, upstreams, upstream_port)
            except Exception:
                # si el upstream falla, devolvemos SERVFAIL vacio
                reply = request.reply()
                reply.header.rcode = RCODE.SERVFAIL
                sock.sendto(reply.pack(), self.client_address)
                return

            # Bloqueo por IP de respuesta (si configuraste IPs)
            if filtro.ips:
                try:
                    parsed = DNSRecord.parse(respuesta)
                    for rr in parsed.rr:
                        if QTYPE[rr.rtype] in ("A", "AAAA"):
                            if filtro.ip_bloqueada(str(rr.rdata)):
                                if log_blocked:
                                    registrar_bloqueo(qname, f"IP {rr.rdata}")
                                sock.sendto(
                                    construir_respuesta_bloqueo(request, block_ip),
                                    self.client_address)
                                return
                except Exception:
                    pass

            sock.sendto(respuesta, self.client_address)

    return DNSHandler


class ServidorUDP(socketserver.ThreadingUDPServer):
    # False: evita que dos instancias compartan el puerto 53 en silencio
    # (en Windows SO_REUSEADDR en UDP reparte paquetes de forma impredecible).
    allow_reuse_address = False
    daemon_threads = True


def main():
    config = cargar_config()
    filtro = Filtro(config)

    addr = (config.get("listen_addr", "127.0.0.1"),
            config.get("listen_port", 53))
    servidor = ServidorUDP(addr, hacer_handler(filtro))

    print(f"[OK] Filtro DNS escuchando en {addr[0]}:{addr[1]} "
          f"(upstream {config['upstream']}).")
    print("     Para detener: Ctrl+C  (o usa desinstalar.ps1 con contrasena).")

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n[..] Detenido por el usuario.")
        servidor.shutdown()


if __name__ == "__main__":
    main()
