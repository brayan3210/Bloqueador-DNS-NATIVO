# Cómo usar el proyecto (guía práctica)

Cubre 3 cosas: **cómo ejecutar los `.ps1`**, **el instalador `.exe`**, y **cómo
funciona el filtro DNS en cualquier red** (con la verificación real).

---

## 1) Cómo ejecutar los archivos `.ps1` (PowerShell)

Los `.ps1` son scripts de PowerShell. **Todos se auto-elevan solos**: al abrirlos
aparece el aviso de administrador (UAC) → dale **Sí**. Tienes 3 formas:

### Forma A — Clic derecho (la más fácil)
1. Clic derecho sobre el archivo (ej. `aplicar_cambios.ps1`).
2. **"Ejecutar con PowerShell"**.
3. Acepta el UAC.

### Forma B — Desde una ventana de PowerShell
1. Abre **PowerShell** (tecla Windows → escribe "PowerShell" → Enter).
2. Ve a la carpeta y ejecútalo:
   ```powershell
   cd "C:\Users\braya\OneDrive\Escritorio\FiltroContenido"
   powershell -ExecutionPolicy Bypass -File .\aplicar_cambios.ps1
   ```
   El `-ExecutionPolicy Bypass` evita el bloqueo de "scripts no firmados".

### Forma C — Dentro de Claude Code
Escribe en el prompt, con el `!` delante:
```
! powershell -ExecutionPolicy Bypass -File "C:\ruta\al\script.ps1"
```

### Qué hace cada `.ps1`
| Script | Para qué |
|---|---|
| `instalar.ps1` | Instala y blinda el **filtro DNS** |
| `blindar_red.ps1` | Refuerza: regla NRPT (DNS en cualquier red) + anti-DoH |
| `aplicar_cambios.ps1` | Aplica listas/contraseña editadas y reinicia el filtro DNS |
| `desinstalar.ps1` | Quita el filtro DNS (**pide contraseña**) |
| `proxy_busquedas\instalar_proxy.ps1` | Instala la **capa de búsquedas** |
| `proxy_busquedas\aplicar_proxy.ps1` | Aplica cambios del catálogo de búsquedas |
| `proxy_busquedas\desactivar_proxy.ps1` | Quita la capa de búsquedas (**pide contraseña**) |

---

## 2) El instalador `.exe` (para instalar todo de una / distribuir)

`instalador\dist\FiltroContenido-Setup.exe` es **un solo archivo** que lleva
DENTRO todo el proyecto. Al ejecutarlo:
1. Pide permisos de administrador (UAC).
2. Muestra los **términos** y exige aceptarlos.
3. Pide una **contraseña** (que la escriba un familiar o una IA y borres el chat).
4. Instala **todos los módulos**: filtro DNS + blindaje + capa de búsquedas.

### Reconstruir el `.exe` (si cambias el código)
```powershell
powershell -ExecutionPolicy Bypass -File .\instalador\construir_exe.ps1
```
Necesita Python + PyInstaller (el script instala PyInstaller solo). Salida en
`instalador\dist\FiltroContenido-Setup.exe`.

### Verificar el `.exe` sin instalar nada
```powershell
.\instalador\dist\FiltroContenido-Setup.exe --check
```
Devuelve código 0 si el proyecto quedó bien empaquetado dentro.

> Nota de comercialización: el filtro corre sobre Python. El instalador intenta
> instalar Python con winget si falta. Para un producto 100% "sin Python en el
> equipo" habría que congelar también el runtime (paso futuro).

---

## 3) La contraseña (destruida) — quitar y volver a poner

Hay **una sola contraseña** (hash SHA-256 en `config.json`) que comparten el
filtro DNS y la capa de búsquedas. Si nadie la sabe (la destruiste), **no quedas
atrapado**:

1. `python configurar_password.py` → escribes una **nueva** (no pide la vieja).
2. `aplicar_cambios.ps1` → la propaga a la copia protegida (la usan ambos filtros).
3. Ya con la nueva:
   - `desinstalar.ps1` quita el DNS.
   - `proxy_busquedas\desactivar_proxy.ps1` quita las búsquedas.
4. **Volver a poner:** corres de nuevo los instaladores (o el `.exe`).

---

## 4) El filtro DNS funciona en CUALQUIER red (verificado)

**Duda común:** "si el DNS del Wi-Fi apunta al router y no a 127.0.0.1, ¿no se
salta el filtro?" **No.** El filtro no depende del DNS del adaptador: usa una
**regla NRPT** que fuerza TODO el DNS del equipo a `127.0.0.1` (el filtro), en
cualquier red y adaptador.

### Cómo comprobarlo tú mismo
```powershell
# 1) ¿Existe la regla que fuerza el DNS al filtro?
Get-DnsClientNrptRule | Where-Object { $_.NameServers -contains "127.0.0.1" }
#    Debe mostrar: Namespace='.'  NameServers=127.0.0.1  Comment=FiltroContenido

# 2) ¿Un dominio porno queda bloqueado? (Resolve-DnsName SÍ respeta NRPT)
Resolve-DnsName pornhub.com -Type A     # -> 0.0.0.0  (BLOQUEADO)
Resolve-DnsName google.com   -Type A     # -> IP real (permitido)
```

> ⚠️ **No uses `nslookup` para probar:** `nslookup` habla **directo al router** y
> **NO respeta la regla NRPT**, así que mostrará IPs reales aunque el filtro esté
> activo. Es una falsa alarma. Usa `Resolve-DnsName` (como hacen los navegadores).

Verificado el 2026-07-22: NRPT activa; `pornhub.com`/`xvideos.com` → `0.0.0.0`;
el filtro escuchando en `127.0.0.1:53`. **Funciona en cualquier red.**

---

## 5) La capa de búsquedas solo toca los buscadores

Para no romper el resto del sistema (winget, banca, Windows Update, YouTube
video), el proxy **solo inspecciona los buscadores** (Google, Bing, YouTube,
DuckDuckGo, Yandex, Brave, Ecosia, Startpage, Qwant). Todo lo demás **pasa sin
interceptar**. Tras instalar, **reinicia el navegador** para que tome el filtro.
