# -*- coding: utf-8 -*-
"""
instalador.py - Instalador GRAFICO del Filtro de Contenido (todo el proyecto PC).

Se compila a un unico .exe con PyInstaller (ver construir_exe.ps1). Al ejecutarlo:
  1. Se auto-eleva a administrador (UAC).
  2. Asistente por pasos (estilo profesional): Bienvenido -> Terminos ->
     Contrasena -> Componentes -> Instalacion -> Finalizacion.
  3. Instala TODO: filtro DNS + blindaje de red + capa de busquedas (proxy).

El .exe lleva DENTRO todo el proyecto (carpeta 'payload') y el instalador de
Python 3.12.0; si el equipo no tiene Python, lo instala solo.

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
    pyi = os.path.join(base, PY_INSTALLER)
    print(("  OK " if os.path.exists(pyi) else "  (sin)"), PY_INSTALLER, "(Python embebido)")
    print("RESULTADO:", "TODO PRESENTE" if ok else "FALTAN ARCHIVOS")
    return 0 if ok else 1


# --------------------------------------------------------------------------
# Python: instalar el oficial EMBEBIDO si el equipo no lo tiene
# --------------------------------------------------------------------------
PY_INSTALLER = "python-3.12.0-amd64.exe"


def _localizar_python(log=None):
    """Devuelve la ruta a python.exe. Tras instalar, el PATH del proceso actual
    no se refresca, asi que buscamos en las rutas estandar y la anexamos al PATH
    para que los procesos hijos (los .ps1) tambien lo encuentren."""
    p = hay_python()
    if p:
        return p
    local = os.environ.get("LOCALAPPDATA", "")
    cands = [
        r"C:\Program Files\Python312\python.exe",
        r"C:\Program Files\Python313\python.exe",
        os.path.join(local, r"Programs\Python\Python312\python.exe"),
        os.path.join(local, r"Programs\Python\Python313\python.exe"),
    ]
    for c in cands:
        if c and os.path.exists(c):
            os.environ["PATH"] = os.path.dirname(c) + os.pathsep + os.environ.get("PATH", "")
            if log:
                log(f"   Python instalado en: {c}")
            return c
    return None


def instalar_python(base, log):
    """Instala Python 3.12.0 desde el instalador oficial EMBEBIDO (sin internet).
    Si por algun motivo no esta embebido, intenta winget. Devuelve ruta o None."""
    emb = os.path.join(base, PY_INSTALLER)
    if os.path.exists(emb):
        log("Python no encontrado. Instalando Python 3.12.0 (incluido)...")
        try:
            subprocess.run([emb, "/quiet", "InstallAllUsers=1",
                            "PrependPath=1", "Include_pip=1"],
                           check=False, timeout=1800)
        except Exception as e:
            log(f"   fallo el instalador incluido: {e}")
    else:
        log("Python no encontrado. Intentando con winget...")
        try:
            subprocess.run(["winget", "install", "--id", "Python.Python.3.12", "-e",
                            "--accept-source-agreements", "--accept-package-agreements"],
                           check=False)
        except Exception as e:
            log(f"   winget fallo: {e}")
    return _localizar_python(log)


# --------------------------------------------------------------------------
# Ejecucion de la instalacion (ya elevado)
# --------------------------------------------------------------------------
def ejecutar_instalacion(password, log):
    base = base_payload()

    # 1) Python (si falta, instalar el 3.12.0 EMBEBIDO -> sin internet ni winget)
    log("Comprobando Python...")
    py = hay_python()
    if not py:
        py = instalar_python(base, log)
    if not py:
        log("ERROR: no se pudo preparar Python. Instalalo desde python.org "
            "(marca 'Add to PATH') y reintenta.")
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
# Interfaz grafica: asistente profesional (ventana sin borde + rail de pasos)
# --------------------------------------------------------------------------
def gui():
    import queue
    import threading
    import tkinter as tk
    import webbrowser
    from tkinter import messagebox, scrolledtext, ttk

    # --- Paleta (oscuro azul) y tipografia ---
    BG = "#0a0e17"; SIDE = "#0c1120"; CARD = "#121826"; CARD2 = "#161d2e"
    LINE = "#212a3d"; BLUE = "#2f7ff0"; BLUE_D = "#2569d0"; BLUE_LT = "#4a9eff"
    TXT = "#eef2f8"; MUT = "#8b95a7"; FAINT = "#5b6577"; GREEN = "#3ecf8e"
    UI = "Segoe UI"; MDL2 = "Segoe MDL2 Assets"; MONO = "Consolas"
    # Glifos de Segoe MDL2 Assets (viene con Windows 10/11)
    G_SHIELD = ""; G_HOME = ""; G_PAGE = ""; G_LOCK = ""
    G_GRID = ""; G_DOWN = ""; G_CHECK = ""; G_SEARCH = ""
    G_GLOBE = ""; G_MIN = ""; G_CLOSE = ""
    GITHUB = "https://github.com/brayan3210"
    PAYPAL = "https://www.paypal.com/donate/?hosted_button_id=ANE8JAX7MG5FE"

    base = base_payload()

    def asset(name):
        for d in (base, os.path.dirname(base)):
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
        return None

    terminos = "No se encontraron los terminos."
    tp = asset("TERMINOS.txt")
    if tp:
        try:
            with open(tp, "r", encoding="utf-8") as f:
                terminos = f.read()
        except Exception:
            pass

    root = tk.Tk()
    root.title(APP_TITLE)
    root.configure(bg=BG)
    root.overrideredirect(True)
    W, H = 960, 620
    sx = (root.winfo_screenwidth() - W) // 2
    sy = max(0, (root.winfo_screenheight() - H) // 3)
    root.geometry(f"{W}x{H}+{sx}+{sy}")
    ic = asset("icono.ico")
    if ic:
        try: root.iconbitmap(ic)
        except Exception: pass

    imgs = {}
    def load_img(name):
        p = asset(name)
        if not p:
            return None
        try:
            im = tk.PhotoImage(file=p); imgs[name] = im; return im
        except Exception:
            return None
    hero_img = load_img("escudo_hero.png")
    pp_img = load_img("paypal.png")

    style = ttk.Style()
    try: style.theme_use("clam")
    except Exception: pass
    style.configure("Blue.Horizontal.TProgressbar", troughcolor=CARD2,
                    bordercolor=CARD2, background=BLUE, lightcolor=BLUE, darkcolor=BLUE)

    def warn(m):
        messagebox.showwarning(APP_TITLE, m)

    def boton(parent, text, cmd, primary=True):
        base_bg = BLUE if primary else CARD2
        hov = BLUE_D if primary else LINE
        fg = "#ffffff" if primary else TXT
        b = tk.Button(parent, text=text, command=cmd, relief="flat", bd=0, cursor="hand2",
                      font=(UI, 10, "bold"), padx=22, pady=8, bg=base_bg, fg=fg,
                      activebackground=hov, activeforeground=fg,
                      highlightthickness=(0 if primary else 1), highlightbackground=LINE)
        b.bind("<Enter>", lambda e: b["state"] == "normal" and b.configure(bg=hov))
        b.bind("<Leave>", lambda e: b["state"] == "normal" and b.configure(bg=base_bg))
        return b

    def clickable(parent, text, fn, fg=BLUE_LT, font=(UI, 9)):
        lb = tk.Label(parent, text=text, bg=parent["bg"], fg=fg, font=font, cursor="hand2")
        lb.bind("<Button-1>", lambda e: fn())
        return lb

    # ---- mover / minimizar / cerrar (ventana sin borde) ----
    def start_move(e): root._mx, root._my = e.x, e.y
    def do_move(e): root.geometry(f"+{e.x_root - root._mx}+{e.y_root - root._my}")
    def on_map(e): root.overrideredirect(True)
    root.bind("<Map>", on_map)

    def minimizar():
        root.overrideredirect(False)
        root.iconify()

    def cerrar():
        if state["installing"]:
            return
        root.destroy()

    # ===================== SIDEBAR =====================
    side = tk.Frame(root, bg=SIDE, width=250)
    side.pack(side="left", fill="y"); side.pack_propagate(False)

    brand = tk.Frame(side, bg=SIDE); brand.pack(fill="x", padx=22, pady=(24, 6))
    tk.Label(brand, text="", bg=SIDE, fg=BLUE, font=(MDL2, 26)).pack(side="left")
    bt = tk.Frame(brand, bg=SIDE); bt.pack(side="left", padx=(10, 0))
    tk.Label(bt, text="Filtro de Contenido", bg=SIDE, fg=TXT, font=(UI, 12, "bold")).pack(anchor="w")
    tk.Label(bt, text="Versión 1.0", bg=SIDE, fg=MUT, font=(UI, 8)).pack(anchor="w")
    for w in (brand, bt):
        w.bind("<Button-1>", start_move); w.bind("<B1-Motion>", do_move)

    STEP_DEFS = [
        ("Bienvenido", "Descripción general", ""),
        ("Términos de uso", "Acuerdo de licencia", ""),
        ("Contraseña", "Clave de protección", ""),
        ("Componentes", "Qué se instalará", ""),
        ("Instalación", "Instalando el programa", ""),
        ("Finalización", "Instalación completada", ""),
    ]
    railc = tk.Canvas(side, bg=SIDE, highlightthickness=0, width=250, height=384)
    railc.pack(fill="x", pady=(16, 0))
    stepitems = []
    for i, (t, s, g) in enumerate(STEP_DEFS):
        cy = 26 + i * 62
        if i < len(STEP_DEFS) - 1:
            railc.create_line(42, cy + 17, 42, cy + 45, fill=LINE, dash=(2, 3))
        circ = railc.create_oval(27, cy - 15, 57, cy + 15, outline=LINE, width=2, fill=SIDE)
        gl = railc.create_text(42, cy, text=g, font=(MDL2, 12), fill=MUT)
        ti = railc.create_text(72, cy - 8, text=t, font=(UI, 10, "bold"), fill=MUT, anchor="w")
        su = railc.create_text(72, cy + 9, text=s, font=(UI, 8), fill=FAINT, anchor="w")
        stepitems.append((circ, gl, ti, su, g))

    def paint_steps(active):
        for i, (circ, gl, ti, su, g) in enumerate(stepitems):
            if i < active:
                railc.itemconfig(circ, outline=BLUE, fill=BLUE)
                railc.itemconfig(gl, text="", fill="#ffffff")
                railc.itemconfig(ti, fill=MUT); railc.itemconfig(su, fill=FAINT)
            elif i == active:
                railc.itemconfig(circ, outline=BLUE, fill=BLUE)
                railc.itemconfig(gl, text=g, fill="#ffffff")
                railc.itemconfig(ti, fill=TXT); railc.itemconfig(su, fill=MUT)
            else:
                railc.itemconfig(circ, outline=LINE, fill=SIDE)
                railc.itemconfig(gl, text=g, fill=MUT)
                railc.itemconfig(ti, fill=MUT); railc.itemconfig(su, fill=FAINT)

    # footer: desarrollador + github + paypal
    foot = tk.Frame(side, bg=SIDE); foot.pack(side="bottom", fill="x", padx=22, pady=16)
    tk.Frame(foot, bg=LINE, height=1).pack(fill="x", pady=(0, 10))
    tk.Label(foot, text="Brayan Cortés", bg=SIDE, fg=TXT, font=(UI, 9, "bold")).pack(anchor="w")
    tk.Label(foot, text="Desarrollador Fullstack", bg=SIDE, fg=MUT, font=(UI, 8)).pack(anchor="w", pady=(0, 8))
    frow = tk.Frame(foot, bg=SIDE); frow.pack(fill="x")
    gh = clickable(frow, "GitHub  ↗", lambda: webbrowser.open(GITHUB), fg=BLUE_LT, font=(UI, 9, "bold"))
    gh.pack(side="left")
    donar = tk.Button(frow, image=pp_img, text=" Donar", compound="left",
                      bg=CARD2, fg=TXT, relief="flat", bd=0, cursor="hand2",
                      font=(UI, 9, "bold"), padx=10, pady=4,
                      activebackground=LINE, activeforeground=TXT,
                      command=lambda: webbrowser.open(PAYPAL))
    donar.pack(side="right")
    donar.bind("<Enter>", lambda e: donar.configure(bg=LINE))
    donar.bind("<Leave>", lambda e: donar.configure(bg=CARD2))

    # ===================== ZONA PRINCIPAL =====================
    mainf = tk.Frame(root, bg=BG); mainf.pack(side="left", fill="both", expand=True)

    ctrl = tk.Frame(mainf, bg=BG); ctrl.place(relx=1.0, x=-4, y=6, anchor="ne")
    def ctrl_btn(glyph, cmd, hov):
        lb = tk.Label(ctrl, text=glyph, bg=BG, fg=MUT, font=(MDL2, 10), cursor="hand2", padx=10, pady=5)
        lb.pack(side="left")
        lb.bind("<Button-1>", lambda e: cmd())
        lb.bind("<Enter>", lambda e: lb.configure(bg=hov, fg="#ffffff"))
        lb.bind("<Leave>", lambda e: lb.configure(bg=BG, fg=MUT))
        return lb
    ctrl_btn("", minimizar, "#1a2130")
    ctrl_btn("", cerrar, "#c0392b")

    head = tk.Frame(mainf, bg=BG); head.pack(fill="x", padx=44, pady=(30, 0))
    htitle = tk.Frame(head, bg=BG); htitle.pack(anchor="w")
    t_sub = tk.StringVar()
    tk.Label(head, textvariable=t_sub, bg=BG, fg=MUT, font=(UI, 10)).pack(anchor="w", pady=(4, 0))
    for w in (head,):
        w.bind("<Button-1>", start_move); w.bind("<B1-Motion>", do_move)

    def set_title(parts):
        for w in htitle.winfo_children():
            w.destroy()
        for txt, col in parts:
            tk.Label(htitle, text=txt, bg=BG, fg=col, font=(UI, 22, "bold")).pack(side="left")

    tk.Frame(mainf, bg=LINE, height=1).pack(fill="x", padx=44, pady=(16, 0))
    body = tk.Frame(mainf, bg=BG); body.pack(fill="both", expand=True, padx=44, pady=(18, 6))

    hero_lbl = tk.Label(mainf, image=hero_img, bg=BG) if hero_img else None

    def icon_circle(parent, glyph, size=46, fg=BLUE_LT, bg=CARD):
        c = tk.Canvas(parent, width=size, height=size, bg=bg, highlightthickness=0)
        c.create_oval(3, 3, size - 3, size - 3, fill=CARD2, outline="")
        c.create_text(size // 2, size // 2, text=glyph, font=(MDL2, int(size * 0.33)), fill=fg)
        return c

    # ---- Pagina 0: Bienvenido ----
    pg0 = tk.Frame(body, bg=BG)
    fcard = tk.Frame(pg0, bg=CARD, highlightthickness=1, highlightbackground=LINE)
    fcard.pack(fill="x")
    feats = [
        ("", "Filtro de contenido avanzado", "Bloquea material pornográfico en tu equipo y mantiene una navegación segura."),
        ("", "Protección en tiempo real", "Filtra búsquedas y sitios web no deseados en todos tus navegadores."),
        ("", "Privacidad y seguridad", "Todo el filtrado ocurre en tu equipo. No recopilamos tus datos."),
    ]
    for idx, (g, t, d) in enumerate(feats):
        r = tk.Frame(fcard, bg=CARD); r.pack(fill="x", padx=20, pady=13)
        icon_circle(r, g).pack(side="left")
        tf = tk.Frame(r, bg=CARD); tf.pack(side="left", fill="x", expand=True, padx=(16, 0))
        tk.Label(tf, text=t, bg=CARD, fg=TXT, font=(UI, 11, "bold"), anchor="w").pack(anchor="w")
        tk.Label(tf, text=d, bg=CARD, fg=MUT, font=(UI, 9), anchor="w", justify="left", wraplength=520).pack(anchor="w")
        if idx < len(feats) - 1:
            tk.Frame(fcard, bg=LINE, height=1).pack(fill="x", padx=20)
    tline = tk.Frame(pg0, bg=BG); tline.pack(fill="x", pady=(16, 0))
    tk.Label(tline, text="", bg=BG, fg=BLUE, font=(MDL2, 10)).pack(side="left")
    tk.Label(tline, text="  Al continuar, aceptas los", bg=BG, fg=MUT, font=(UI, 9)).pack(side="left")
    clickable(tline, " Términos de uso", lambda: go(1)).pack(side="left")
    tk.Label(tline, text="y la", bg=BG, fg=MUT, font=(UI, 9)).pack(side="left", padx=(4, 0))
    clickable(tline, "Política de privacidad.", lambda: go(1)).pack(side="left", padx=(4, 0))

    # ---- Pagina 1: Terminos ----
    pg1 = tk.Frame(body, bg=BG)
    tbox = scrolledtext.ScrolledText(pg1, wrap="word", bg=CARD, fg=TXT, relief="flat",
                                     font=(MONO, 9), padx=16, pady=14, bd=0,
                                     highlightthickness=1, highlightbackground=LINE, highlightcolor=LINE)
    tbox.pack(fill="both", expand=True)
    tbox.insert("1.0", terminos); tbox.configure(state="disabled")
    acepta = tk.BooleanVar(value=False)
    tk.Checkbutton(pg1, text="  He leído y acepto los términos", variable=acepta,
                   bg=BG, fg=TXT, selectcolor=CARD2, activebackground=BG, activeforeground=BLUE_LT,
                   font=(UI, 10), anchor="w", bd=0, highlightthickness=0).pack(fill="x", pady=(14, 0))

    # ---- Pagina 2: Contrasena ----
    pg2 = tk.Frame(body, bg=BG)
    pcard = tk.Frame(pg2, bg=CARD, highlightthickness=1, highlightbackground=LINE); pcard.pack(fill="x")
    pin = tk.Frame(pcard, bg=CARD); pin.pack(fill="x", padx=26, pady=22)

    def campo(parent, label):
        tk.Label(parent, text=label, bg=CARD, fg=MUT, font=(UI, 10)).pack(anchor="w", pady=(6, 3))
        e = tk.Entry(parent, show="●", bg=CARD2, fg=TXT, insertbackground=BLUE, relief="flat", font=(UI, 12))
        e.pack(fill="x", ipady=8)
        return e

    e1 = campo(pin, "Contraseña (mínimo 8 caracteres)")
    e2 = campo(pin, "Confirmar contraseña")
    tips = tk.Frame(pg2, bg=BG); tips.pack(fill="x", pady=(16, 0))
    for line in ["Solo se guarda su huella (SHA-256); el texto nunca se almacena.",
                 "Consejo: que la escriba un familiar de confianza y no te la diga,",
                 "o que la genere una IA, la pegues aquí y luego borres ese chat.",
                 "Con ella podrás desactivar el filtro en el futuro."]:
        tk.Label(tips, text="•  " + line, bg=BG, fg=MUT, font=(UI, 9), anchor="w").pack(anchor="w", pady=1)

    # ---- Pagina 3: Componentes ----
    pg3 = tk.Frame(body, bg=BG)
    ccard = tk.Frame(pg3, bg=CARD, highlightthickness=1, highlightbackground=LINE); ccard.pack(fill="x")
    comps = [
        ("Filtro DNS", "Bloquea ~260.000 dominios porno en cualquier red."),
        ("Capa de búsquedas", "Filtra lo que escribes en Google/Bing/YouTube, sin SafeSearch."),
        ("Blindaje de red", "Fuerza el DNS al filtro (NRPT) y desactiva DNS-over-HTTPS."),
        ("Python 3.12", "Se instala solo si tu equipo aún no lo tiene."),
        ("Protección y arranque", "Candado por contraseña y arranque automático con Windows."),
    ]
    for idx, (t, d) in enumerate(comps):
        r = tk.Frame(ccard, bg=CARD); r.pack(fill="x", padx=22, pady=10)
        tk.Label(r, text="", bg=CARD, fg=GREEN, font=(MDL2, 13)).pack(side="left")
        tf = tk.Frame(r, bg=CARD); tf.pack(side="left", fill="x", expand=True, padx=(14, 0))
        tk.Label(tf, text=t, bg=CARD, fg=TXT, font=(UI, 11, "bold"), anchor="w").pack(anchor="w")
        tk.Label(tf, text=d, bg=CARD, fg=MUT, font=(UI, 9), anchor="w", justify="left", wraplength=520).pack(anchor="w")
        if idx < len(comps) - 1:
            tk.Frame(ccard, bg=LINE, height=1).pack(fill="x", padx=22)

    # ---- Pagina 4: Instalacion ----
    pg4 = tk.Frame(body, bg=BG)
    prog = ttk.Progressbar(pg4, style="Blue.Horizontal.TProgressbar", mode="indeterminate")
    prog.pack(fill="x", pady=(6, 12))
    logbox = scrolledtext.ScrolledText(pg4, height=10, wrap="word", bg="#070b13", fg="#9fb6d6",
                                       relief="flat", font=(MONO, 8), padx=12, pady=10, bd=0,
                                       highlightthickness=1, highlightbackground=LINE)
    logbox.pack(fill="both", expand=True)

    # ---- Pagina 5: Finalizacion ----
    pg5 = tk.Frame(body, bg=BG)
    fin_wrap = tk.Frame(pg5, bg=BG); fin_wrap.pack(expand=True)
    if hero_img:
        tk.Label(fin_wrap, image=hero_img, bg=BG).pack(pady=(0, 6))
    tk.Label(fin_wrap, text="¡Todo listo!", bg=BG, fg=TXT, font=(UI, 18, "bold")).pack()
    tk.Label(fin_wrap, text="El filtro ya está activo. Reinicia el navegador para activar\nel bloqueo de búsquedas.",
             bg=BG, fg=MUT, font=(UI, 10), justify="center").pack(pady=(6, 0))

    # ===================== NAVEGACION =====================
    navbar = tk.Frame(mainf, bg=BG); navbar.pack(fill="x", padx=44, pady=(0, 24))
    lang = tk.Frame(navbar, bg=CARD2, highlightthickness=1, highlightbackground=LINE)
    tk.Label(lang, text="", bg=CARD2, fg=MUT, font=(MDL2, 9)).pack(side="left", padx=(10, 5), pady=6)
    tk.Label(lang, text="Español", bg=CARD2, fg=TXT, font=(UI, 9)).pack(side="left", padx=(0, 12))
    lang.pack(side="left")

    state = {"i": 0, "installing": False, "done": False}
    btn_next = boton(navbar, "Siguiente  ›", lambda: on_next(), primary=True)
    btn_next.pack(side="right")
    btn_cancel = boton(navbar, "Cancelar", cerrar, primary=False)
    btn_cancel.pack(side="right", padx=(0, 10))
    btn_back = boton(navbar, "‹  Atrás", lambda: go(state["i"] - 1), primary=False)
    btn_back.pack(side="right", padx=(0, 10))

    pages = [pg0, pg1, pg2, pg3, pg4, pg5]
    META = [
        ([("Bienvenido a ", TXT), ("Filtro de Contenido", BLUE_LT)], "Este asistente te guiará en la instalación del programa."),
        ([("Términos de uso", TXT)], "Léelos con calma y acéptalos para continuar."),
        ([("Contraseña", TXT)], "La necesitarás para desactivar el filtro más adelante."),
        ([("Componentes", TXT)], "Esto es lo que se instalará en tu equipo."),
        ([("Instalación", TXT)], "Instalando todos los módulos. No cierres la ventana."),
        ([("Finalización", TXT)], "Instalación completada."),
    ]

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
        i = max(0, min(5, i))
        for p in pages:
            p.pack_forget()
        pages[i].pack(fill="both", expand=True)
        set_title(META[i][0]); t_sub.set(META[i][1])
        paint_steps(i)
        if hero_lbl:
            if i == 0:
                hero_lbl.place(relx=1.0, x=-24, y=70, anchor="ne")
            else:
                hero_lbl.place_forget()
        installing = state["installing"]
        btn_back.configure(state=("normal" if (i in (1, 2, 3) and not installing) else "disabled"))
        btn_cancel.configure(state=("disabled" if installing else "normal"))
        if i == 3:
            btn_next.configure(text="Instalar  ›")
        elif i == 4:
            btn_next.configure(text="Instalando…")
        elif i == 5:
            btn_next.configure(text="Finalizar")
        else:
            btn_next.configure(text="Siguiente  ›")
        state["i"] = i

    def on_next():
        if state["installing"]:
            return
        i = state["i"]
        if i == 0:
            go(1)
        elif i == 1:
            if not acepta.get():
                warn("Debes aceptar los términos para continuar."); return
            go(2)
        elif i == 2:
            p1, p2 = e1.get(), e2.get()
            if len(p1) < 8:
                warn("La contraseña debe tener al menos 8 caracteres."); return
            if p1 != p2:
                warn("Las contraseñas no coinciden."); return
            go(3)
        elif i == 3:
            go(4); start_install(e1.get())
        elif i == 4:
            if not state["done"]:
                start_install(e1.get())
        elif i == 5:
            root.destroy()

    def start_install(pwd):
        state["installing"] = True
        btn_next.configure(state="disabled", text="Instalando…")
        btn_back.configure(state="disabled"); btn_cancel.configure(state="disabled")
        paint_steps(4)
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
                btn_cancel.configure(state="normal")
                btn_next.configure(state="normal")
                if ok:
                    go(5)
                else:
                    t_sub.set("Hubo un problema. Revisa el registro de abajo.")
                    btn_next.configure(text="Reintentar")
            root.after(0, fin)

        threading.Thread(target=worker, daemon=True).start()

    go(0)
    root.after(80, lambda: (root.deiconify(), root.lift(), root.focus_force()))
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
