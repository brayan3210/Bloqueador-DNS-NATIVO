# instalar.ps1 - Instala y BLINDA el filtro de contenido.
#  - Copia el programa a C:\ProgramData\FiltroContenido (oculto, protegido).
#  - El usuario normal NO puede borrar esa carpeta (solo administrador elevado).
#  - Cambia el DNS del sistema a 127.0.0.1.
#  - Tarea programada como SYSTEM que arranca con Windows y se reinicia sola.
# Se auto-eleva a administrador. NO necesita ejecutarse de nuevo tras instalar.

# --- Auto-elevacion ---
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Pidiendo permisos de administrador..." -ForegroundColor Yellow
    Start-Process powershell "-ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

$ErrorActionPreference = "Stop"
$SRC     = Split-Path -Parent $MyInvocation.MyCommand.Definition
$INSTALL = "C:\ProgramData\FiltroContenido"
$USUARIO = $env:USERNAME

# Crear config.json desde la plantilla si no existe (primera vez tras clonar)
if (-not (Test-Path "$SRC\config.json") -and (Test-Path "$SRC\config.example.json")) {
    Copy-Item "$SRC\config.example.json" "$SRC\config.json"
    Write-Host "config.json creado desde config.example.json"
}

Write-Host "=== Instalando y blindando el Filtro de Contenido ===" -ForegroundColor Cyan

# --- Resolver Python ---
$python  = (Get-Command python).Source
$pythonw = $python -replace 'python\.exe$','pythonw.exe'
if (-not (Test-Path $pythonw)) { $pythonw = $python }
Write-Host "Python: $python"

# --- 1) Dependencias ---
Write-Host "`n[1/6] Instalando dependencias (dnslib, requests)..." -ForegroundColor Cyan
& $python -m pip install --upgrade pip
& $python -m pip install -r "$SRC\requirements.txt"

# --- 2) Copiar a carpeta protegida ---
Write-Host "`n[2/6] Copiando a $INSTALL ..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $INSTALL | Out-Null
New-Item -ItemType Directory -Force -Path "$INSTALL\logs" | Out-Null
robocopy $SRC $INSTALL /E /XD "__pycache__" "logs" /XF "*.pyc" "dns_backup.json" ".parar" | Out-Null

# --- 3) Descargar listas grandes (reales, >250k dominios) ---
Write-Host "`n[3/6] Descargando listas de bloqueo (puede tardar)..." -ForegroundColor Cyan
& $python "$INSTALL\actualizar_listas.py"

# --- 4) DNS del sistema -> 127.0.0.1 (guardando respaldo) ---
Write-Host "`n[4/6] Cambiando DNS del sistema a 127.0.0.1..." -ForegroundColor Cyan
$adapters = Get-NetAdapter | Where-Object { $_.Status -eq "Up" }
$backup = @()
foreach ($a in $adapters) {
    $cur = (Get-DnsClientServerAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4).ServerAddresses
    $backup += [PSCustomObject]@{ ifIndex = $a.ifIndex; servers = $cur }
    Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ServerAddresses "127.0.0.1"
    Write-Host "   - $($a.Name): DNS -> 127.0.0.1"
}
$backup | ConvertTo-Json | Out-File "$INSTALL\dns_backup.json" -Encoding utf8
Clear-DnsClientCache

# --- 5) Blindaje: ocultar + permisos (el usuario no puede borrar) ---
Write-Host "`n[5/6] Aplicando blindaje (ocultar + permisos)..." -ForegroundColor Cyan
attrib +h $INSTALL
# SYSTEM (S-1-5-18) y Administradores (S-1-5-32-544) = control total.
# El usuario normal solo lectura+ejecucion: no puede borrar ni modificar.
icacls $INSTALL /inheritance:r /T | Out-Null
icacls $INSTALL /grant:r "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" "${USUARIO}:(OI)(CI)RX" /T | Out-Null

# --- 6) Tarea programada (SYSTEM, arranque + reinicio automatico) ---
Write-Host "`n[6/6] Creando tarea de arranque (SYSTEM)..." -ForegroundColor Cyan
$vigilante = Join-Path $INSTALL "vigilante.py"
$action    = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$vigilante`""
$trigStart = New-ScheduledTaskTrigger -AtStartup
$trigLogon = New-ScheduledTaskTrigger -AtLogOn
$principalTask = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName "FiltroContenido" -Action $action -Trigger $trigStart,$trigLogon -Principal $principalTask -Settings $settings -Force | Out-Null

if (Test-Path "$INSTALL\.parar") { Remove-Item "$INSTALL\.parar" -Force }
Start-ScheduledTask -TaskName "FiltroContenido"

Write-Host "`n=== LISTO. Filtro ACTIVO y blindado. ===" -ForegroundColor Green
Write-Host "Programa protegido en: $INSTALL (oculto)"
Write-Host "Editas listas en el Escritorio y aplicas con:  aplicar_cambios.ps1"
Write-Host "Desactivar (requiere contrasena):  desinstalar.ps1"
Pause
