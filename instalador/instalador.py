# -*- coding: utf-8 -*-
"""
instalador.py - Instalador GRAFICO del Filtro de Contenido (todo el proyecto PC).

Se compila a un unico .exe con PyInstaller (ver construir_exe.ps1). Al ejecutarlo:
  1. Se auto-eleva a administrador (UAC).
  2. Asistente por pasos: Terminos -> Contrasena -> Instalacion.
  3. Instala TODO: filtro DNS + blindaje de red + capa de busquedas (proxy).

El .exe lleva DENTRO todo el proyecto (carpeta 'payload'). En un equipo nuevo,
si falta Python intenta instalarlo con winget.

Modo verificacion (no instala nada):   instalador.exe --check
"""

import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys

APP_TITLE = "Filtro de Contenido — Instalador"


# --------------------------------------------------------------------------
# Utilidades base
# --------------------------------------------------------------------------
def base_payload():
    """Carpeta con TODO el proyecto (dentro del exe, o junto al script en dev)."""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "payload")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "payload")


def es_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relanzar_elevado():
    """Relanza este mismo programa pedido permisos de administrador."""
    if getattr(sys, "frozen", False):
        exe, params = sys.executable, " ".join(sys.argv[1:])
    else:
        exe = sys.executable
        params = " ".join(['"' + os.path.abspath(__file__) + '"'] + sys.argv[1:])
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    return rc > 32  # >32 = exito


def hash_password(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def hay_python():
    return shutil.which("python") or shutil.which("py")


# --------------------------------------------------------------------------
# Verificacion (para pruebas): instalador.exe --check
# --------------------------------------------------------------------------
def modo_check():
    base = base_payload()
    req = [
        os.path.join(base, "filtro.py"),
        os.path.join(base, "instalar.ps1"),
        os.path.join(base, "config.example.json"),
        os.path.join(base, "proxy_busquedas", "instalar_proxy.ps1"),
        os.path.join(base, "proxy_busquedas", "motor_busqueda.py"),
    ]
    print("payload:", base)
    ok = True
    for r in req:
        existe = os.path.exists(r)
        ok = ok and existe
        print(("  OK " if existe else "  FALTA "), os.path.relpath(r, base))
    print("RESULTADO:", "TODO PRESENTE" if ok else "FALTAN ARCHIVOS")
    return 0 if ok else 1


# --------------------------------------------------------------------------
# Ejecucion de la instalacion (ya elevado)
# --------------------------------------------------------------------------
def ejecutar_instalacion(password, log):
    base = base_payload()

    # 1) Python
    log("Comprobando Python...")
    py = hay_python()
    if not py:
        log("Python no encontrado. Intentando instalarlo con winget...")
        try:
            subprocess.run(
                ["winget", "install", "--id", "Python.Python.3.12", "-e",
                 "--accept-source-agreements", "--accept-package-agreements"],
                check=False)
        except Exception as e:
            log(f"No se pudo instalar Python automaticamente: {e}")
        py = hay_python()
    if not py:
        log("ERROR: se necesita Python 3.8+ instalado. Instalalo desde "
            "python.org (marca 'Add to PATH') y reintenta.")
        return False
    log(f"Python: {py}")

    # 2) config.json con la contrasena (antes de instalar, para que se copie)
    log("Fijando la contrasena (hash SHA-256)...")
    cfg_path = os.path.join(base, "config.json")
    ejemplo = os.path.join(base, "config.example.json")
    try:
        if os.path.exists(ejemplo):
            with open(ejemplo, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        else:
            cfg = {}
        cfg["password_hash"] = hash_password(password)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        log(f"ERROR escribiendo config.json: {e}")
        return False

    # 3) Instalar filtro DNS + blindaje de red + capa de busquedas
    ps = shutil.which("powershell") or "powershell"
    for script, desc in [
        ("instalar.ps1", "Filtro DNS + blindaje"),
        ("blindar_red.ps1", "Reforzar red (NRPT + anti-DoH)"),
        (os.path.join("proxy_busquedas", "instalar_proxy.ps1"), "Capa de busquedas"),
    ]:
        ruta = os.path.join(base, script)
        if not os.path.exists(ruta):
            log(f"(omitido, no existe: {script})")
            continue
        log(f"Instalando: {desc} ...")
        try:
            # Ya estamos elevados: los .ps1 detectan admin y no re-piden UAC.
            r = subprocess.run(
                [ps, "-ExecutionPolicy", "Bypass", "-NoProfile", "-File", ruta],
                cwd=base, input="\n", capture_output=True, text=True, timeout=1200)
            cola = (r.stdout or "").strip().splitlines()[-3:]
            for ln in cola:
                log("   " + ln)
            if r.returncode != 0:
                log(f"   (aviso: {desc} devolvio codigo {r.returncode})")
        except Exception as e:
            log(f"   ERROR en {desc}: {e}")
    log("")
    log("=== INSTALACION TERMINADA ===")
    log("Reinicia el navegador para que tome el filtro de busquedas.")
    return True


# --------------------------------------------------------------------------
# Interfaz grafica: asistente por pasos
# --------------------------------------------------------------------------
def gui():
    import queue
    import threading
    import tkinter as tk
    from tkinter import messagebox, scrolledtext, ttk

    # --- Paleta (guardian: navy + oro) y tipografia ---
    BG = "#0b1220"; RAIL = "#0a1526"; CARD = "#121c31"; CARD2 = "#16233d"
    GOLD = "#e6b955"; GOLD_D = "#c99f3f"; TXT = "#e8edf7"; MUT = "#9fb0cc"
    LINE = "#22304d"; GREEN = "#5fd0a0"; FAINT = "#4a5a78"
    UI = "Segoe UI"; MONO = "Consolas"

    base = base_payload()
    terminos = "No se encontraron los terminos."
    tpath = os.path.join(base, "TERMINOS.txt")
    if not os.path.exists(tpath):
        tpath = os.path.join(os.path.dirname(base), "TERMINOS.txt")
    try:
        with open(tpath, "r", encoding="utf-8") as f:
            terminos = f.read()
    except Exception:
        pass

    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry("900x620")
    root.minsize(860, 580)
    root.configure(bg=BG)
    for icop in (os.path.join(base, "icono.ico"), os.path.join(os.path.dirname(base), "icono.ico")):
        try:
            if os.path.exists(icop):
                root.iconbitmap(icop); break
        except Exception:
            pass

    style = ttk.Style()
    try: style.theme_use("clam")
    except Exception: pass
    style.configure("Gold.Horizontal.TProgressbar", troughcolor=CARD,
                    bordercolor=CARD, background=GOLD, lightcolor=GOLD, darkcolor=GOLD)

    def boton(parent, text, cmd, primary=True):
        base_bg = GOLD if primary else CARD
        hov = GOLD_D if primary else LINE
        b = tk.Button(parent, text=text, command=cmd, relief="flat", bd=0, cursor="hand2",
                      font=(UI, 11, "bold"), padx=26, pady=9,
                      bg=base_bg, fg=(BG if primary else TXT),
                      activebackground=hov, activeforeground=(BG if primary else TXT))
        b.bind("<Enter>", lambda e: (b["state"] == "normal") and b.configure(bg=hov))
        b.bind("<Leave>", lambda e: (b["state"] == "normal") and b.configure(bg=base_bg))
        return b

    # ===================== RAIL de pasos =====================
    rail = tk.Frame(root, bg=RAIL, width=240)
    rail.pack(side="left", fill="y"); rail.pack_propagate(False)
    tk.Label(rail, text="🛡", bg=RAIL, fg=GOLD, font=(UI, 40)).pack(pady=(30, 0))
    tk.Label(rail, text="Filtro de Contenido", bg=RAIL, fg=TXT, font=(UI, 13, "bold")).pack()
    tk.Label(rail, text="Herramienta de autocontrol", bg=RAIL, fg=MUT, font=(UI, 8)).pack(pady=(0, 26))

    step_widgets = []
    for (n, name) in [("1", "Términos"), ("2", "Contraseña"), ("3", "Instalación")]:
        row = tk.Frame(rail, bg=RAIL); row.pack(fill="x", padx=24, pady=7)
        dot = tk.Label(row, text=n, bg=RAIL, fg=MUT, font=(UI, 10, "bold"), width=3, anchor="center")
        dot.pack(side="left")
        lb = tk.Label(row, text=name, bg=RAIL, fg=MUT, font=(UI, 11)); lb.pack(side="left", padx=(6, 0))
        step_widgets.append((dot, lb))
    tk.Label(rail, text="Sin SafeSearch · todo local\nBrayan Cortés · Licencia MIT",
             bg=RAIL, fg=FAINT, font=(UI, 8), justify="left").pack(side="bottom", anchor="w", padx=24, pady=18)

    # ===================== ZONA principal =====================
    main = tk.Frame(root, bg=BG); main.pack(side="left", fill="both", expand=True)
    head = tk.Frame(main, bg=BG); head.pack(fill="x", padx=40, pady=(32, 0))
    t_title = tk.StringVar(); t_sub = tk.StringVar()
    tk.Label(head, textvariable=t_title, bg=BG, fg=TXT, font=(UI, 21, "bold")).pack(anchor="w")
    tk.Label(head, textvariable=t_sub, bg=BG, fg=MUT, font=(UI, 10)).pack(anchor="w", pady=(3, 0))
    tk.Frame(main, bg=LINE, height=1).pack(fill="x", padx=40, pady=(18, 0))
    body = tk.Frame(main, bg=BG); body.pack(fill="both", expand=True, padx=40, pady=20)

    # --- Pagina 1: Terminos ---
    pg_terms = tk.Frame(body, bg=BG)
    tbox = scrolledtext.ScrolledText(pg_terms, wrap="word", bg=CARD, fg=TXT, relief="flat",
                                     font=(MONO, 9), padx=16, pady=14, bd=0,
                                     highlightthickness=1, highlightbackground=LINE, highlightcolor=LINE)
    tbox.pack(fill="both", expand=True)
    tbox.insert("1.0", terminos); tbox.configure(state="disabled")
    acepta = tk.BooleanVar(value=False)
    tk.Checkbutton(pg_terms, text="  He leído y acepto los términos", variable=acepta,
                   bg=BG, fg=TXT, selectcolor=CARD, activebackground=BG, activeforeground=GOLD,
                   font=(UI, 10), anchor="w", bd=0, highlightthickness=0).pack(fill="x", pady=(14, 0))

    # --- Pagina 2: Contrasena ---
    pg_pwd = tk.Frame(body, bg=BG)
    card = tk.Frame(pg_pwd, bg=CARD, highlightthickness=1, highlightbackground=LINE)
    card.pack(fill="x")
    inner = tk.Frame(card, bg=CARD); inner.pack(fill="x", padx=26, pady=22)

    def campo(parent, label):
        tk.Label(parent, text=label, bg=CARD, fg=MUT, font=(UI, 10)).pack(anchor="w", pady=(6, 2))
        e = tk.Entry(parent, show="●", bg=CARD2, fg=TXT, insertbackground=GOLD, relief="flat", font=(UI, 12))
        e.pack(fill="x", ipady=7)
        return e

    e1 = campo(inner, "Contraseña (mínimo 8 caracteres)")
    e2 = campo(inner, "Confirmar contraseña")
    tips = tk.Frame(pg_pwd, bg=BG); tips.pack(fill="x", pady=(18, 0))
    for line in ["Solo se guarda su huella (SHA-256); el texto nunca se almacena.",
                 "Consejo: que la escriba un familiar de confianza y no te la diga,",
                 "o que la genere una IA, la pegues aquí y luego borres ese chat.",
                 "Con ella podrás desactivar el filtro en el futuro."]:
        tk.Label(tips, text="•  " + line, bg=BG, fg=MUT, font=(UI, 9), anchor="w").pack(anchor="w", pady=1)

    # --- Pagina 3: Instalacion ---
    pg_inst = tk.Frame(body, bg=BG)
    resumen = tk.Frame(pg_inst, bg=BG); resumen.pack(fill="x")
    for item in ["Filtro DNS — bloquea dominios porno (~260k) en cualquier red",
                 "Blindaje de red — NRPT + desactiva DNS-over-HTTPS",
                 "Capa de búsquedas — Google/Bing/YouTube, sin SafeSearch",
                 "Protección con tu contraseña + arranque automático con Windows"]:
        tk.Label(resumen, text="✓   " + item, bg=BG, fg=TXT, font=(UI, 10), anchor="w").pack(anchor="w", pady=2)
    prog = ttk.Progressbar(pg_inst, style="Gold.Horizontal.TProgressbar", mode="indeterminate")
    prog.pack(fill="x", pady=(18, 10))
    logbox = scrolledtext.ScrolledText(pg_inst, height=8, wrap="word", bg="#0a1526", fg="#9fead0",
                                       relief="flat", font=(MONO, 8), padx=12, pady=10, bd=0,
                                       highlightthickness=1, highlightbackground=LINE)
    logbox.pack(fill="both", expand=True)

    # ===================== Navegacion =====================
    nav = tk.Frame(main, bg=BG); nav.pack(fill="x", padx=40, pady=(0, 26))
    state = {"i": 0, "installing": False, "done": False}
    btn_back = boton(nav, "Atrás", lambda: go(state["i"] - 1), primary=False)
    btn_back.pack(side="left")
    btn_next = boton(nav, "Siguiente", lambda: on_next())
    btn_next.pack(side="right")

    pages = [pg_terms, pg_pwd, pg_inst]
    meta = [("Términos de uso", "Léelos con calma y acéptalos para continuar."),
            ("Crea tu contraseña", "La necesitarás para desactivar el filtro más adelante."),
            ("Instalación", "Se instalarán todos los módulos en tu equipo.")]

    # log seguro entre hilos (la instalacion corre en un hilo)
    q = queue.Queue()
    def log(msg): q.put(str(msg))
    def drain():
        try:
            while True:
                m = q.get_nowait()
                logbox.configure(state="normal"); logbox.insert("end", m + "\n")
                logbox.see("end"); logbox.configure(state="disabled")
        except queue.Empty:
            pass
        root.after(120, drain)
    root.after(120, drain)

    def go(i):
        i = max(0, min(2, i))
        for p in pages: p.pack_forget()
        pages[i].pack(fill="both", expand=True)
        t_title.set(meta[i][0]); t_sub.set(meta[i][1])
        for j, (dot, lb) in enumerate(step_widgets):
            c = GREEN if j < i else (GOLD if j == i else MUT)
            dot.configure(fg=c); lb.configure(fg=(TXT if j == i else c))
        btn_back.configure(state=("disabled" if (i == 0 or state["installing"]) else "normal"))
        btn_next.configure(text=("Finalizar" if state["done"] else "Instalar ahora") if i == 2 else "Siguiente")
        state["i"] = i

    def on_next():
        i = state["i"]
        if i == 0:
            if not acepta.get():
                messagebox.showwarning(APP_TITLE, "Debes aceptar los términos para continuar."); return
            go(1)
        elif i == 1:
            p1, p2 = e1.get(), e2.get()
            if len(p1) < 8:
                messagebox.showwarning(APP_TITLE, "La contraseña debe tener al menos 8 caracteres."); return
            if p1 != p2:
                messagebox.showwarning(APP_TITLE, "Las contraseñas no coinciden."); return
            go(2)
        else:
            if state["done"]:
                root.destroy(); return
            iniciar_instalacion(e1.get())

    def iniciar_instalacion(pwd):
        state["installing"] = True
        btn_next.configure(state="disabled"); btn_back.configure(state="disabled")
        t_sub.set("Instalando… no cierres esta ventana.")
        prog.configure(mode="indeterminate"); prog.start(12)

        def worker():
            ok = False
            try:
                ok = ejecutar_instalacion(pwd, log)
            except Exception as e:
                log(f"ERROR: {e}")

            def fin():
                prog.stop(); prog.configure(mode="determinate"); prog["value"] = 100
                state["installing"] = False; state["done"] = bool(ok)
                btn_next.configure(state="normal")
                if ok:
                    t_sub.set("Instalación completada. Reinicia el navegador.")
                    btn_next.configure(text="Finalizar")
                else:
                    t_sub.set("Hubo un problema. Revisa el registro de abajo.")
                    btn_next.configure(text="Reintentar")
                    btn_back.configure(state="normal")
            root.after(0, fin)

        threading.Thread(target=worker, daemon=True).start()

    go(0)
    if "--gui-selftest" in sys.argv:
        root.after(700, root.destroy)   # prueba: abrir y cerrar sin bloquear
    root.mainloop()


# --------------------------------------------------------------------------
def main():
    if "--check" in sys.argv:
        return modo_check()
    if "--gui-selftest" in sys.argv:
        gui(); return 0   # prueba de interfaz, sin elevar
    # Elevar a administrador antes de mostrar nada (instalar requiere admin).
    if not es_admin():
        if relanzar_elevado():
            return 0
        # si no se pudo elevar, seguimos igual y la instalacion avisara.
    gui()
    return 0


if __name__ == "__main__":
    sys.exit(main())
