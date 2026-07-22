# -*- coding: utf-8 -*-
"""
instalador.py - Instalador GRAFICO del Filtro de Contenido (todo el proyecto PC).

Interfaz profesional (CustomTkinter) estilo Windows 11 / Fluent: ventana nativa
con esquinas redondeadas, tema oscuro azul, dos columnas (stepper + panel).

Al ejecutarlo:
  1. Se auto-eleva a administrador (UAC).
  2. Asistente por pasos: Bienvenido -> Terminos -> Ubicacion -> Componentes
     (contrasena) -> Instalacion -> Finalizacion.
  3. Instala TODO: filtro DNS + blindaje de red + capa de busquedas (proxy).

El .exe lleva DENTRO todo el proyecto (carpeta 'payload') y el instalador de
Python 3.12.0; si el equipo no tiene Python, lo instala solo.

Modos de prueba (no instalan nada):  --check   |   --gui-selftest
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
            r = subprocess.run(
                [ps, "-ExecutionPolicy", "Bypass", "-NoProfile", "-File", ruta],
                cwd=base, input="\n", capture_output=True, text=True, timeout=1200)
            for ln in (r.stdout or "").strip().splitlines()[-3:]:
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
# Interfaz grafica (CustomTkinter) — estilo Windows 11 / Fluent
# --------------------------------------------------------------------------
def gui():
    import queue
    import threading
    import tkinter as tk
    import webbrowser

    import customtkinter as ctk
    from PIL import Image

    # ---- Paleta (spec del usuario) ----
    C_LEFT = "#07111E"; C_RIGHT = "#101A2A"; C_MID = "#0D1726"
    C_CARD = "#111E31"; C_HOVER = "#18263D"; C_TXT = "#FFFFFF"; C_SEC = "#AEB8C7"
    C_FAINT = "#7E8796"; C_BLUE = "#2E89FF"; C_BLUE2 = "#4BA3FF"; C_BORDER = "#1F2C42"
    C_INPUT = "#0C1728"

    # ---- Glifos Segoe MDL2 Assets (por codepoint = ASCII puro) ----
    G_SHIELD = chr(0xEA18); G_HOME = chr(0xE80F); G_PAGE = chr(0xE7C3)
    G_FOLDER = chr(0xE8B7); G_GRID = chr(0xE71D); G_DOWN = chr(0xE896)
    G_CHECK = chr(0xE73E); G_LOCK = chr(0xE72E); G_SEARCH = chr(0xE721)
    G_GLOBE = chr(0xE774); G_CHEVDOWN = chr(0xE70D)

    GITHUB = "https://github.com/brayan3210"
    PAYPAL = "https://www.paypal.com/donate/?hosted_button_id=ANE8JAX7MG5FE"
    INSTALL_DIR = r"C:\ProgramData\FiltroContenido"

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

    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root.title(APP_TITLE)
    root.configure(fg_color=C_RIGHT)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    W = max(1100, min(1480, sw - 120)); H = max(720, min(920, sh - 120))
    root.geometry(f"{W}x{H}+{(sw - W) // 2}+{max(0, (sh - H) // 3)}")
    root.minsize(1080, 700)
    ico = asset("icono.ico")
    if ico:
        try: root.iconbitmap(ico)
        except Exception: pass

    def F(sz, w="normal"): return ctk.CTkFont("Segoe UI", sz, w)
    def FM(sz): return ctk.CTkFont("Segoe MDL2 Assets", sz)

    def cimg(name, size):
        p = asset(name)
        if not p:
            return None
        try:
            return ctk.CTkImage(Image.open(p), size=size)
        except Exception:
            return None
    hero_ck = cimg("escudo_hero.png", (172, 182))
    hero_sm = cimg("escudo_hero.png", (128, 135))
    pp_ck = cimg("paypal.png", (18, 18))
    deco_ck = cimg("deco.png", (320, 266))

    root.grid_columnconfigure(0, weight=0)
    root.grid_columnconfigure(1, weight=1)
    root.grid_rowconfigure(0, weight=1)

    # ============================ PANEL IZQUIERDO ============================
    left = ctk.CTkFrame(root, width=370, corner_radius=0, fg_color=C_LEFT)
    left.grid(row=0, column=0, sticky="nsew"); left.grid_propagate(False)

    if deco_ck:  # decoracion tenue al fondo
        deco_lbl = ctk.CTkLabel(left, text="", image=deco_ck, fg_color="transparent")
        deco_lbl.place(relx=0.0, rely=1.0, anchor="sw")
        deco_lbl.lower()

    brand = ctk.CTkFrame(left, fg_color="transparent")
    brand.pack(fill="x", padx=32, pady=(34, 0))
    ctk.CTkLabel(brand, text=G_SHIELD, font=FM(30), text_color=C_BLUE).pack(side="left")
    bt = ctk.CTkFrame(brand, fg_color="transparent"); bt.pack(side="left", padx=(12, 0))
    ctk.CTkLabel(bt, text="Filtro de Contenido", font=F(17, "bold"), text_color=C_TXT).pack(anchor="w")
    ctk.CTkLabel(bt, text="Versión 1.0", font=F(11), text_color=C_FAINT).pack(anchor="w")

    STEPS = [
        ("Bienvenido", "Descripción general", G_HOME),
        ("Términos de uso", "Acuerdo de licencia", G_PAGE),
        ("Ubicación", "Carpeta de instalación", G_FOLDER),
        ("Componentes", "Opciones de instalación", G_GRID),
        ("Instalación", "Instalando el programa", G_DOWN),
        ("Finalización", "Instalación completada", G_CHECK),
    ]
    steps_c = tk.Canvas(left, bg=C_LEFT, highlightthickness=0, width=370)
    steps_c.pack(fill="both", expand=True, padx=0, pady=(46, 0))
    step_items = []
    for i, (t, s, g) in enumerate(STEPS):
        cy = 40 + i * 74
        cx = 52
        if i < len(STEPS) - 1:
            steps_c.create_line(cx, cy + 22, cx, cy + 52, fill=C_BORDER, dash=(2, 4))
        glow = steps_c.create_oval(cx - 26, cy - 26, cx + 26, cy + 26, outline="", fill=C_LEFT)
        circ = steps_c.create_oval(cx - 19, cy - 19, cx + 19, cy + 19, outline=C_BORDER, width=2, fill=C_MID)
        gl = steps_c.create_text(cx, cy, text=g, font=("Segoe MDL2 Assets", 14), fill=C_FAINT)
        ti = steps_c.create_text(cx + 40, cy - 9, text=t, font=("Segoe UI", 11, "bold"), fill=C_SEC, anchor="w")
        su = steps_c.create_text(cx + 40, cy + 9, text=s, font=("Segoe UI", 8), fill=C_FAINT, anchor="w")
        step_items.append((glow, circ, gl, ti, su, g))

    def paint_steps(active):
        for i, (glow, circ, gl, ti, su, g) in enumerate(step_items):
            if i < active:      # completado
                steps_c.itemconfig(glow, fill=C_LEFT)
                steps_c.itemconfig(circ, outline=C_BLUE, fill="#123256")
                steps_c.itemconfig(gl, text=G_CHECK, fill=C_BLUE2)
                steps_c.itemconfig(ti, fill=C_SEC); steps_c.itemconfig(su, fill=C_FAINT)
            elif i == active:   # activo (glow azul)
                steps_c.itemconfig(glow, fill="#0f2440")
                steps_c.itemconfig(circ, outline=C_BLUE2, fill=C_BLUE)
                steps_c.itemconfig(gl, text=g, fill="#ffffff")
                steps_c.itemconfig(ti, fill=C_TXT); steps_c.itemconfig(su, fill=C_SEC)
            else:               # pendiente
                steps_c.itemconfig(glow, fill=C_LEFT)
                steps_c.itemconfig(circ, outline=C_BORDER, fill=C_MID)
                steps_c.itemconfig(gl, text=g, fill=C_FAINT)
                steps_c.itemconfig(ti, fill=C_SEC); steps_c.itemconfig(su, fill=C_FAINT)

    # footer izquierdo: desarrollador + github + paypal
    foot = ctk.CTkFrame(left, fg_color="transparent")
    foot.pack(side="bottom", fill="x", padx=32, pady=22)
    ctk.CTkFrame(foot, height=1, fg_color=C_BORDER).pack(fill="x", pady=(0, 12))
    ctk.CTkLabel(foot, text="Brayan Cortés", font=F(12, "bold"), text_color=C_TXT).pack(anchor="w")
    ctk.CTkLabel(foot, text="Desarrollador Fullstack", font=F(10), text_color=C_SEC).pack(anchor="w", pady=(0, 10))
    frow = ctk.CTkFrame(foot, fg_color="transparent"); frow.pack(fill="x")
    gh = ctk.CTkLabel(frow, text="GitHub  ↗", font=F(10, "bold"), text_color=C_BLUE2, cursor="hand2")
    gh.pack(side="left"); gh.bind("<Button-1>", lambda e: webbrowser.open(GITHUB))
    ctk.CTkButton(frow, text="  Donar", image=pp_ck, compound="left", width=90, height=30,
                  corner_radius=10, font=F(10, "bold"), fg_color=C_CARD, hover_color=C_HOVER,
                  text_color=C_TXT, command=lambda: webbrowser.open(PAYPAL)).pack(side="right")

    # ============================ PANEL DERECHO ============================
    right = ctk.CTkFrame(root, corner_radius=0, fg_color=C_RIGHT)
    right.grid(row=0, column=1, sticky="nsew")
    right.grid_rowconfigure(1, weight=1)
    right.grid_columnconfigure(0, weight=1)

    # -- header (titulo + subtitulo + escudo) --
    header = ctk.CTkFrame(right, fg_color="transparent")
    header.grid(row=0, column=0, sticky="ew", padx=48, pady=(42, 0))
    header.grid_columnconfigure(0, weight=1)
    htitle = ctk.CTkFrame(header, fg_color="transparent"); htitle.grid(row=0, column=0, sticky="w")
    sub_lbl = ctk.CTkLabel(header, text="", font=F(13), text_color=C_SEC, justify="left")
    sub_lbl.grid(row=1, column=0, sticky="w", pady=(10, 0))
    hero_lbl = ctk.CTkLabel(header, text="", image=hero_ck)
    hero_lbl.grid(row=0, column=1, rowspan=2, sticky="e", padx=(24, 0))

    def set_title(parts):
        for w in htitle.winfo_children():
            w.destroy()
        for txt, col in parts:
            ctk.CTkLabel(htitle, text=txt, font=F(30, "bold"), text_color=col).pack(side="left")

    # -- contenedor de contenido (cambia por paso) --
    content = ctk.CTkFrame(right, fg_color="transparent")
    content.grid(row=1, column=0, sticky="nsew", padx=48, pady=(26, 0))

    def card(parent):
        return ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=18,
                            border_width=1, border_color=C_BORDER)

    def feature_row(parent, glyph, title, desc):
        r = ctk.CTkFrame(parent, fg_color="transparent")
        r.pack(fill="x", padx=26, pady=15)
        circ = ctk.CTkFrame(r, width=52, height=52, corner_radius=26, fg_color=C_MID)
        circ.pack(side="left"); circ.pack_propagate(False)
        ctk.CTkLabel(circ, text=glyph, font=FM(20), text_color=C_BLUE2).place(relx=0.5, rely=0.5, anchor="center")
        tf = ctk.CTkFrame(r, fg_color="transparent"); tf.pack(side="left", fill="x", expand=True, padx=(18, 0))
        ctk.CTkLabel(tf, text=title, font=F(14, "bold"), text_color=C_TXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(tf, text=desc, font=F(11), text_color=C_SEC, anchor="w", justify="left",
                     wraplength=560).pack(anchor="w", pady=(3, 0))

    # ----- Pagina 0: Bienvenido -----
    pg0 = ctk.CTkFrame(content, fg_color="transparent")
    fcard = card(pg0); fcard.pack(fill="x")
    feature_row(fcard, G_SEARCH, "Filtro de contenido avanzado",
                "Bloquea material pornográfico en tu equipo y mantiene una navegación segura.")
    ctk.CTkFrame(fcard, height=1, fg_color=C_BORDER).pack(fill="x", padx=26)
    feature_row(fcard, G_SHIELD, "Protección en tiempo real",
                "Filtra búsquedas y sitios web no deseados en todos tus navegadores.")
    ctk.CTkFrame(fcard, height=1, fg_color=C_BORDER).pack(fill="x", padx=26)
    feature_row(fcard, G_LOCK, "Privacidad y seguridad",
                "No recopilamos tus datos. Todo el filtrado ocurre en tu equipo.")
    tline = ctk.CTkFrame(pg0, fg_color="transparent"); tline.pack(fill="x", pady=(22, 0))
    ctk.CTkLabel(tline, text=G_SHIELD, font=FM(13), text_color=C_BLUE).pack(side="left")
    ctk.CTkLabel(tline, text="  Al continuar, aceptas los", font=F(11), text_color=C_SEC).pack(side="left")
    for tx in (" Términos de uso", " y la ", "Política de privacidad."):
        es_link = tx.strip() in ("Términos de uso", "Política de privacidad.")
        lb = ctk.CTkLabel(tline, text=tx, font=F(11, "bold" if es_link else "normal"),
                          text_color=(C_BLUE2 if es_link else C_SEC))
        lb.pack(side="left")
        if es_link:
            lb.configure(cursor="hand2"); lb.bind("<Button-1>", lambda e: go(1))

    # ----- Pagina 1: Terminos -----
    pg1 = ctk.CTkFrame(content, fg_color="transparent")
    tbox = ctk.CTkTextbox(pg1, fg_color=C_CARD, border_color=C_BORDER, border_width=1,
                          corner_radius=16, font=("Consolas", 12), text_color=C_SEC, wrap="word")
    tbox.pack(fill="both", expand=True)
    tbox.insert("1.0", terminos); tbox.configure(state="disabled")
    acepta = ctk.BooleanVar(value=False)
    ctk.CTkCheckBox(pg1, text="  He leído y acepto los términos", variable=acepta,
                    font=F(12), text_color=C_TXT, fg_color=C_BLUE, hover_color=C_BLUE2,
                    border_color=C_BORDER, corner_radius=6).pack(anchor="w", pady=(16, 0))

    # ----- Pagina 2: Ubicacion -----
    pg2 = ctk.CTkFrame(content, fg_color="transparent")
    ucard = card(pg2); ucard.pack(fill="x")
    ur = ctk.CTkFrame(ucard, fg_color="transparent"); ur.pack(fill="x", padx=26, pady=22)
    ucirc = ctk.CTkFrame(ur, width=52, height=52, corner_radius=26, fg_color=C_MID)
    ucirc.pack(side="left"); ucirc.pack_propagate(False)
    ctk.CTkLabel(ucirc, text=G_FOLDER, font=FM(20), text_color=C_BLUE2).place(relx=0.5, rely=0.5, anchor="center")
    uf = ctk.CTkFrame(ur, fg_color="transparent"); uf.pack(side="left", fill="x", expand=True, padx=(18, 0))
    ctk.CTkLabel(uf, text="Carpeta de instalación", font=F(14, "bold"), text_color=C_TXT, anchor="w").pack(anchor="w")
    ctk.CTkLabel(uf, text=INSTALL_DIR, font=("Consolas", 12), text_color=C_BLUE2, anchor="w").pack(anchor="w", pady=(4, 0))
    ctk.CTkLabel(pg2, text="Se instala en una carpeta protegida del sistema (oculta y sin permiso de\n"
                          "borrado para el usuario normal). La ubicación es fija para blindar el filtro.",
                 font=F(11), text_color=C_SEC, justify="left").pack(anchor="w", pady=(18, 0))

    # ----- Pagina 3: Componentes + contrasena -----
    pg3 = ctk.CTkFrame(content, fg_color="transparent")
    ccard = card(pg3); ccard.pack(fill="x")
    comps = [
        ("Filtro DNS", "Bloquea ~260.000 dominios porno en cualquier red."),
        ("Capa de búsquedas", "Filtra lo que escribes en Google/Bing/YouTube, sin SafeSearch."),
        ("Blindaje de red + Python 3.12", "Fuerza el DNS al filtro; instala Python si falta."),
    ]
    for idx, (t, d) in enumerate(comps):
        r = ctk.CTkFrame(ccard, fg_color="transparent"); r.pack(fill="x", padx=26, pady=12)
        ctk.CTkLabel(r, text=G_CHECK, font=FM(15), text_color="#3ECF8E").pack(side="left")
        tf = ctk.CTkFrame(r, fg_color="transparent"); tf.pack(side="left", fill="x", expand=True, padx=(14, 0))
        ctk.CTkLabel(tf, text=t, font=F(13, "bold"), text_color=C_TXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(tf, text=d, font=F(11), text_color=C_SEC, anchor="w", justify="left", wraplength=540).pack(anchor="w")
        if idx < len(comps) - 1:
            ctk.CTkFrame(ccard, height=1, fg_color=C_BORDER).pack(fill="x", padx=26)
    pwd_wrap = ctk.CTkFrame(pg3, fg_color="transparent"); pwd_wrap.pack(fill="x", pady=(16, 0))
    ctk.CTkLabel(pwd_wrap, text="Clave de protección  (mínimo 8 caracteres)", font=F(11), text_color=C_SEC).pack(anchor="w")
    prow = ctk.CTkFrame(pwd_wrap, fg_color="transparent"); prow.pack(fill="x", pady=(6, 0))
    e1 = ctk.CTkEntry(prow, show="●", height=40, corner_radius=10, fg_color=C_INPUT,
                      border_color=C_BORDER, font=F(12), placeholder_text="Contraseña")
    e1.pack(side="left", fill="x", expand=True, padx=(0, 8))
    e2 = ctk.CTkEntry(prow, show="●", height=40, corner_radius=10, fg_color=C_INPUT,
                      border_color=C_BORDER, font=F(12), placeholder_text="Confirmar")
    e2.pack(side="left", fill="x", expand=True)
    ctk.CTkLabel(pg3, text="Que la escriba un familiar de confianza o una IA y luego borres el chat. "
                          "Solo se guarda su huella (SHA-256).",
                 font=F(10), text_color=C_FAINT, justify="left", wraplength=640).pack(anchor="w", pady=(8, 0))

    # ----- Pagina 4: Instalacion -----
    pg4 = ctk.CTkFrame(content, fg_color="transparent")
    prog = ctk.CTkProgressBar(pg4, mode="indeterminate", progress_color=C_BLUE, height=10, corner_radius=6)
    prog.pack(fill="x", pady=(4, 14))
    logbox = ctk.CTkTextbox(pg4, fg_color="#070d17", border_color=C_BORDER, border_width=1,
                            corner_radius=14, font=("Consolas", 11), text_color="#8FB4DE", wrap="word")
    logbox.pack(fill="both", expand=True)

    # ----- Pagina 5: Finalizacion -----
    pg5 = ctk.CTkFrame(content, fg_color="transparent")
    fwrap = ctk.CTkFrame(pg5, fg_color="transparent"); fwrap.pack(expand=True)
    if hero_sm:
        ctk.CTkLabel(fwrap, text="", image=hero_sm).pack(pady=(0, 10))
    ctk.CTkLabel(fwrap, text="¡Todo listo!", font=F(22, "bold"), text_color=C_TXT).pack()
    ctk.CTkLabel(fwrap, text="El filtro ya está activo. Reinicia el navegador para activar\nel bloqueo de búsquedas.",
                 font=F(12), text_color=C_SEC, justify="center").pack(pady=(8, 0))

    pages = [pg0, pg1, pg2, pg3, pg4, pg5]
    META = [
        ([("Bienvenido a ", C_TXT), ("Filtro de Contenido", C_BLUE2)], "Este asistente te guiará en la instalación del programa."),
        ([("Términos de uso", C_TXT)], "Léelos con calma y acéptalos para continuar."),
        ([("Ubicación", C_TXT)], "Dónde se instalará el programa en tu equipo."),
        ([("Componentes", C_TXT)], "Lo que se instalará y tu clave de protección."),
        ([("Instalación", C_TXT)], "Instalando todos los módulos. No cierres la ventana."),
        ([("Finalización", C_TXT)], "Instalación completada."),
    ]

    # ============================ PIE (footer) ============================
    footer = ctk.CTkFrame(right, fg_color="transparent")
    footer.grid(row=2, column=0, sticky="ew", padx=48, pady=(18, 30))
    ctk.CTkFrame(footer, height=1, fg_color=C_BORDER).pack(fill="x", pady=(0, 16))
    bar = ctk.CTkFrame(footer, fg_color="transparent"); bar.pack(fill="x")

    lang = ctk.CTkFrame(bar, fg_color=C_CARD, corner_radius=10, border_width=1, border_color=C_BORDER)
    lang.pack(side="left")
    ctk.CTkLabel(lang, text=G_GLOBE, font=FM(12), text_color=C_SEC).pack(side="left", padx=(12, 6), pady=8)
    ctk.CTkLabel(lang, text="Español", font=F(11), text_color=C_TXT).pack(side="left")
    ctk.CTkLabel(lang, text=G_CHEVDOWN, font=FM(10), text_color=C_FAINT).pack(side="left", padx=(8, 12))

    state = {"i": 0, "installing": False, "done": False}
    btn_next = ctk.CTkButton(bar, text="Siguiente", width=140, height=42, corner_radius=12,
                             font=F(12, "bold"), fg_color=C_BLUE, hover_color=C_BLUE2,
                             command=lambda: on_next())
    btn_next.pack(side="right")
    btn_cancel = ctk.CTkButton(bar, text="Cancelar", width=120, height=42, corner_radius=12,
                               font=F(12, "bold"), fg_color=C_CARD, hover_color=C_HOVER,
                               text_color=C_SEC, border_width=1, border_color=C_BORDER,
                               command=lambda: cerrar())
    btn_cancel.pack(side="right", padx=(0, 12))
    btn_back = ctk.CTkButton(bar, text="Atrás", width=100, height=42, corner_radius=12,
                             font=F(12, "bold"), fg_color=C_CARD, hover_color=C_HOVER,
                             text_color=C_SEC, border_width=1, border_color=C_BORDER,
                             command=lambda: go(state["i"] - 1))
    btn_back.pack(side="right", padx=(0, 12))

    def cerrar():
        if not state["installing"]:
            root.destroy()

    def _warn(msg):
        from tkinter import messagebox
        messagebox.showwarning(APP_TITLE, msg)

    # ---- log seguro entre hilos ----
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
        set_title(META[i][0]); sub_lbl.configure(text=META[i][1])
        paint_steps(i)
        if i == 0:
            hero_lbl.grid()
        else:
            hero_lbl.grid_remove()
        installing = state["installing"]
        btn_back.configure(state=("normal" if (i in (1, 2, 3) and not installing) else "disabled"))
        btn_cancel.configure(state=("disabled" if installing else "normal"))
        if i == 3:
            btn_next.configure(text="Instalar")
        elif i == 4:
            btn_next.configure(text="Instalando…")
        elif i == 5:
            btn_next.configure(text="Finalizar")
        else:
            btn_next.configure(text="Siguiente")
        state["i"] = i

    def start_install(pwd):
        state["installing"] = True
        btn_next.configure(state="disabled", text="Instalando…")
        btn_back.configure(state="disabled"); btn_cancel.configure(state="disabled")
        paint_steps(4)
        prog.configure(mode="indeterminate"); prog.start()

        def worker():
            ok = False
            try:
                ok = ejecutar_instalacion(pwd, log)
            except Exception as e:
                log(f"ERROR: {e}")

            def fin():
                prog.stop(); prog.configure(mode="determinate"); prog.set(1.0)
                state["installing"] = False; state["done"] = bool(ok)
                btn_cancel.configure(state="normal"); btn_next.configure(state="normal")
                if ok:
                    go(5)
                else:
                    sub_lbl.configure(text="Hubo un problema. Revisa el registro de abajo.")
                    btn_next.configure(text="Reintentar")
            root.after(0, fin)

        threading.Thread(target=worker, daemon=True).start()

    def on_next():
        if state["installing"]:
            return
        i = state["i"]
        if i in (0, 2):
            go(i + 1)
        elif i == 1:
            if not acepta.get():
                _warn("Debes aceptar los términos para continuar."); return
            go(2)
        elif i == 3:
            p1, p2 = e1.get(), e2.get()
            if len(p1) < 8:
                _warn("La contraseña debe tener al menos 8 caracteres."); return
            if p1 != p2:
                _warn("Las contraseñas no coinciden."); return
            go(4); start_install(p1)
        elif i == 4:
            if not state["done"]:
                start_install(e1.get())
        elif i == 5:
            root.destroy()

    go(0)
    if "--gui-selftest" in sys.argv:
        root.after(800, root.destroy)   # prueba: abrir y cerrar sin bloquear
    root.mainloop()


# --------------------------------------------------------------------------
def main():
    if "--check" in sys.argv:
        return modo_check()
    if "--gui-selftest" in sys.argv:
        gui(); return 0   # prueba de interfaz, sin elevar
    if not es_admin():
        if relanzar_elevado():
            return 0
    gui()
    return 0


if __name__ == "__main__":
    sys.exit(main())
