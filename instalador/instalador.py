# -*- coding: utf-8 -*-
"""
instalador.py - Instalador GRAFICO del Filtro de Contenido (todo el proyecto PC).

Se compila a un unico .exe con PyInstaller (ver construir_exe.ps1). Al ejecutarlo:
  1. Se auto-eleva a administrador (UAC).
  2. Muestra los TERMINOS y exige aceptarlos.
  3. Pide una CONTRASENA (la escribe un familiar o una IA y se borra el chat).
  4. Instala TODO: filtro DNS + blindaje de red + capa de busquedas (proxy).

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
import tempfile

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

    # 3) Instalar filtro DNS + blindaje de red
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
# Interfaz grafica
# --------------------------------------------------------------------------
def gui():
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox

    NAVY = "#0b1220"; CARD = "#121c31"; GOLD = "#e6b955"; TXT = "#e8edf7"

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
    root.geometry("720x640")
    root.configure(bg=NAVY)

    tk.Label(root, text="🛡️  Filtro de Contenido", font=("Segoe UI", 18, "bold"),
             fg=GOLD, bg=NAVY).pack(pady=(16, 2))
    tk.Label(root, text="Instalador del proyecto completo (PC)",
             font=("Segoe UI", 10), fg=TXT, bg=NAVY).pack()

    # Terminos
    tk.Label(root, text="Términos de uso:", font=("Segoe UI", 10, "bold"),
             fg=TXT, bg=NAVY).pack(anchor="w", padx=20, pady=(12, 2))
    box = scrolledtext.ScrolledText(root, height=13, wrap="word",
                                    bg=CARD, fg=TXT, insertbackground=TXT,
                                    relief="flat", font=("Consolas", 9))
    box.pack(fill="both", expand=False, padx=20)
    box.insert("1.0", terminos)
    box.configure(state="disabled")

    acepta = tk.BooleanVar(value=False)
    tk.Checkbutton(root, text="He leído y acepto los términos",
                   variable=acepta, fg=TXT, bg=NAVY, selectcolor=CARD,
                   activebackground=NAVY, activeforeground=GOLD,
                   font=("Segoe UI", 10)).pack(anchor="w", padx=20, pady=(8, 4))

    # Contrasena
    frm = tk.Frame(root, bg=NAVY)
    frm.pack(fill="x", padx=20)
    tk.Label(frm, text="Contraseña (mín. 8):", fg=TXT, bg=NAVY,
             font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", pady=3)
    e1 = tk.Entry(frm, show="*", width=28, bg=CARD, fg=TXT, insertbackground=TXT,
                  relief="flat"); e1.grid(row=0, column=1, padx=8)
    tk.Label(frm, text="Confirmar:", fg=TXT, bg=NAVY,
             font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", pady=3)
    e2 = tk.Entry(frm, show="*", width=28, bg=CARD, fg=TXT, insertbackground=TXT,
                  relief="flat"); e2.grid(row=1, column=1, padx=8)
    tk.Label(root, text="Consejo: que la escriba un familiar o una IA y luego borres el chat.",
             fg="#9fb0cc", bg=NAVY, font=("Segoe UI", 8)).pack(anchor="w", padx=20)

    log_box = scrolledtext.ScrolledText(root, height=7, wrap="word", bg="#0a1526",
                                        fg="#9fead0", relief="flat",
                                        font=("Consolas", 8))
    log_box.pack(fill="both", expand=True, padx=20, pady=(10, 6))

    def log(msg):
        log_box.configure(state="normal")
        log_box.insert("end", msg + "\n")
        log_box.see("end")
        log_box.configure(state="disabled")
        root.update_idletasks()

    def instalar():
        if not acepta.get():
            messagebox.showwarning(APP_TITLE, "Debes aceptar los términos.")
            return
        p1, p2 = e1.get(), e2.get()
        if len(p1) < 8:
            messagebox.showwarning(APP_TITLE, "La contraseña debe tener al menos 8 caracteres.")
            return
        if p1 != p2:
            messagebox.showwarning(APP_TITLE, "Las contraseñas no coinciden.")
            return
        btn.configure(state="disabled")
        ok = ejecutar_instalacion(p1, log)
        if ok:
            messagebox.showinfo(APP_TITLE, "Instalación terminada.\nReinicia el navegador.")
        else:
            messagebox.showerror(APP_TITLE, "Hubo un problema. Revisa el registro.")
            btn.configure(state="normal")

    btn = tk.Button(root, text="Instalar todo", command=instalar,
                    bg=GOLD, fg=NAVY, font=("Segoe UI", 11, "bold"),
                    relief="flat", padx=20, pady=6, cursor="hand2")
    btn.pack(pady=(0, 14))

    root.mainloop()


# --------------------------------------------------------------------------
def main():
    if "--check" in sys.argv:
        return modo_check()
    # Elevar a administrador antes de mostrar nada (instalar requiere admin).
    if not es_admin():
        if relanzar_elevado():
            return 0
        # si no se pudo elevar, seguimos igual y la instalacion avisara.
    gui()
    return 0


if __name__ == "__main__":
    sys.exit(main())
