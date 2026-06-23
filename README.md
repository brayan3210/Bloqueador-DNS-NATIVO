# 🛡️ Bloqueador DNS Nativo

> Filtro de contenido **local y nativo** para Windows que bloquea pornografía (y lo que tú definas) a nivel **DNS**, funciona en **cualquier red** y está diseñado como herramienta de **autocontrol**: difícil de desactivar en un impulso.

![Platform](https://img.shields.io/badge/plataforma-Windows-0078D6)
![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB)
![License](https://img.shields.io/badge/licencia-MIT-green)
![Status](https://img.shields.io/badge/estado-funcional-success)

---

## 📖 ¿Qué es?

Un **servidor DNS local** escrito en Python que se instala en tu propia máquina.
Todo dominio que el equipo intenta abrir pasa por él; si está en las listas de
bloqueo o contiene una palabra clave que definas, **se deniega la conexión**
(responde `0.0.0.0`). El resto del tráfico navega con total normalidad.

No es un servicio en la nube ni depende de terceros: **es tuyo y corre en tu PC**.
No usa el SafeSearch de Google (que tiende a sobre-bloquear ciencia/anatomía):
hace su **propio filtrado** apuntando solo a contenido porno.

> ⚠️ **Aviso.** Esta herramienta modifica el DNS del sistema, crea una tarea
> programada con privilegios de SYSTEM y protege su propia carpeta. Está pensada
> para **tu propio equipo** y como apoyo de autocontrol. Úsala bajo tu
> responsabilidad. El "no se puede desinstalar" es **fricción fuerte, no
> imposibilidad**: siendo administrador siempre podrás removerla (ver
> [Recuperación](#-recuperación--desinstalación)).

---

## ✨ Características

- 🚫 **+250.000 dominios porno** reales (listas públicas StevenBlack + Hagezi, se descargan solas).
- 🔑 **Bloqueo por palabra clave**: cualquier dominio que contenga tus términos.
- 🌐 **Funciona en cualquier red/adaptador** gracias a una regla **NRPT** que fuerza todo el DNS a `127.0.0.1`.
- 🕳️ **Anti-evasión DoH**: desactiva DNS-over-HTTPS en Edge/Chrome/Firefox y bloquea sus servidores.
- 🔒 **Blindaje**: instalado oculto en `C:\ProgramData`, con permisos donde el usuario normal no puede borrarlo; arranca con Windows y se reinicia solo.
- 🔐 **Candado por contraseña** (SHA-256) para desactivarlo.
- 📝 **Log** de todo lo bloqueado.

---

## ⚙️ ¿Cómo funciona?

```
   Apps / Navegador
          │  consulta DNS (puerto 53)
          ▼
   127.0.0.1  ──►  filtro.py  (servidor DNS local)
                      │
            ┌─────────┴──────────┐
            ▼                    ▼
   ¿dominio en listas        Permitido → reenvía a
   o palabra clave?          1.1.1.1 / 1.0.0.1 (con reintentos)
            │                    │
            ▼                    ▼
     responde 0.0.0.0      respuesta real al cliente
     (conexión denegada)
```

- **`filtro.py`** — el servidor DNS: decide bloquear/permitir y reenvía lo permitido.
- **`vigilante.py`** — relanza el filtro si se cae o lo cierran.
- **Tarea programada `FiltroContenido`** — corre como SYSTEM, arranca con Windows (`AtStartup` + `AtLogon`) y se reinicia automáticamente.
- **Regla NRPT + DNS estático** — todo el DNS del sistema va al filtro, en cualquier red.
- **Políticas de registro** — desactivan DoH en los navegadores.

---

## 📦 Requisitos

- Windows 10/11
- [Python 3.8+](https://www.python.org/downloads/) (en el PATH)
- Permisos de administrador (para instalar)

---

## 🚀 Instalación

```powershell
# 1) Clonar
git clone https://github.com/brayan3210/Bloqueador-DNS-NATIVO.git
cd Bloqueador-DNS-NATIVO

# 2) (Opcional pero recomendado) definir contraseña para poder desactivarlo
python configurar_password.py

# 3) Instalar y blindar (pide permisos de administrador)
#    Clic derecho en instalar.ps1 -> "Ejecutar con PowerShell"
#    o:
powershell -ExecutionPolicy Bypass -File .\instalar.ps1

# 4) (Opcional) blindar la red para CUALQUIER adaptador + matar DoH
powershell -ExecutionPolicy Bypass -File .\blindar_red.ps1
```

El instalador crea `config.json` a partir de `config.example.json`, instala las
dependencias, descarga las listas, copia el programa a `C:\ProgramData\FiltroContenido`,
cambia el DNS a `127.0.0.1` y registra el arranque automático.

> 💡 **Autocontrol real:** para que de verdad funcione contra el impulso, pide a
> una persona de confianza que escriba **ella** la contraseña y no te la diga.

---

## 🧭 Uso

| Acción | Comando |
|---|---|
| Agregar palabras/dominios | Edita los `.txt` en `listas/` y ejecuta `aplicar_cambios.ps1` |
| Actualizar listas grandes | `python actualizar_listas.py` |
| Ver bloqueos | `C:\ProgramData\FiltroContenido\logs\bloqueados.log` |
| Desactivar (pide contraseña) | `desinstalar.ps1` |

---

## 🔓 Recuperación / Desinstalación

Como eres administrador, **siempre** puedes quitarlo; es deliberadamente trabajoso.

**Método A — contraseña nueva (no necesitas la vieja):**
```powershell
python configurar_password.py        # defines una nueva
powershell -ExecutionPolicy Bypass -File .\aplicar_cambios.ps1   # la aplica
powershell -ExecutionPolicy Bypass -File .\desinstalar.ps1       # desinstala
```

**Método B — manual (PowerShell como Administrador):**
```powershell
Get-DnsClientNrptRule | ? { $_.Comment -eq "FiltroContenido" } | % { Remove-DnsClientNrptRule -Name $_.Name -Force }
Unregister-ScheduledTask -TaskName "FiltroContenido" -Confirm:$false
Get-CimInstance Win32_Process | ? { $_.Name -eq 'pythonw.exe' -and $_.CommandLine -match 'FiltroContenido' } | % { Stop-Process -Id $_.ProcessId -Force }
Get-NetAdapter | ? { $_.Status -eq "Up" } | % { Set-DnsClientServerAddress -InterfaceIndex $_.ifIndex -ResetServerAddresses }
takeown /F "C:\ProgramData\FiltroContenido" /R /D Y; icacls "C:\ProgramData\FiltroContenido" /reset /T
attrib -h "C:\ProgramData\FiltroContenido"; Remove-Item "C:\ProgramData\FiltroContenido" -Recurse -Force
Clear-DnsClientCache
```

---

## 🧠 Modelo de seguridad (honesto)

- **Fail-closed:** si el filtro no arranca, no hay DNS hasta que vuelva (el
  vigilante lo relanza). Para el objetivo del proyecto, eso es deseable.
- **Fricción, no imposibilidad:** el dueño/administrador del equipo siempre puede
  removerlo con esfuerzo. El blindaje impide el borrado casual e impulsivo.
- **Límite técnico:** bloquea **destinos** (páginas), no el **texto** que escribes
  dentro del buscador (eso viaja cifrado; requeriría interceptar HTTPS/MITM, fuera
  de alcance). Aun así, el destino porno queda bloqueado.

---

## 🗂️ Estructura del proyecto

```
Bloqueador-DNS-NATIVO/
├── filtro.py                 # Servidor DNS que filtra (núcleo)
├── vigilante.py              # Relanza el filtro si se cae
├── actualizar_listas.py      # Descarga listas públicas de bloqueo
├── configurar_password.py    # Define/cambia la contraseña
├── instalar.ps1              # Instala y blinda todo
├── aplicar_cambios.ps1       # Aplica listas/código + reinicia
├── blindar_red.ps1           # NRPT + anti-DoH + todos los adaptadores
├── desinstalar.ps1           # Desinstala (pide contraseña)
├── config.example.json       # Plantilla de configuración
├── requirements.txt          # Dependencias (dnslib, requests)
└── listas/
    ├── palabras_clave.txt
    ├── dominios_personalizados.txt
    ├── ips_bloqueadas.txt
    └── doh_bypass.txt
```

---

## 🛣️ Roadmap

- [x] **Windows**: servidor DNS local, blindaje, NRPT, anti-DoH, autocontrol.
- [ ] **Android (APK)**: misma idea de filtrado DNS pero en el propio teléfono
  mediante `VpnService` (estilo Blokada/RethinkDNS), con bloqueo de dominios +
  palabras clave y `Device Admin` para dificultar la desinstalación. *(Planeado;
  reutilizará el enfoque y las listas de la versión PC.)*

---

## 📄 Licencia

[MIT](LICENSE) © 2026 Brayan Cortés Leytón

---

> Hecho como proyecto personal de autocontrol. Si te sirve, una ⭐ ayuda a que más gente lo encuentre.
