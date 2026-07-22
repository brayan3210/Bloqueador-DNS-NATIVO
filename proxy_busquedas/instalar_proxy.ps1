# instalar_proxy.ps1 - Instala la CAPA EXTRA: bloqueo de BUSQUEDAS por palabra.
#
# Que hace (todo local, en TU equipo; no usa SafeSearch):
#   1) Instala mitmproxy (proxy con inspeccion TLS).
#   2) Genera un certificado raiz local y lo instala en Windows (para poder
#      leer el TEXTO de tus busquedas en HTTPS).
#   3) Pone el proxy del sistema en 127.0.0.1:<puerto>.
#   4) Desactiva QUIC/HTTP3 (si no, Chrome hablaria por un canal no inspeccionable).
#   5) Copia el modulo a la carpeta protegida y crea una tarea SYSTEM que lo
#      mantiene vivo (arranca con Windows y se reinicia solo).
#
# NO toca el filtro DNS: es una capa aparte que se suma. Se auto-eleva a admin.
# Para quitarla (con contrasena):  desactivar_proxy.ps1

# --- Auto-elevacion ---
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Pidiendo permisos de administrador..." -ForegroundColor Yellow
    Start-Process powershell "-ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

$ErrorActionPreference = "Stop"
$MOD          = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ROOT         = Split-Path -Parent $MOD
$INSTALL_BASE = "C:\ProgramData\FiltroContenido"
$INSTALL      = Join-Path $INSTALL_BASE "proxy_busquedas"
$CONFDIR      = Join-Path $INSTALL "mitmproxy"
$USUARIO      = $env:USERNAME

Write-Host "=== Instalando capa de bloqueo de BUSQUEDAS ===" -ForegroundColor Cyan

# --- Python / pythonw ---
$python  = (Get-Command python).Source
$pythonw = $python -replace 'python\.exe$','pythonw.exe'
if (-not (Test-Path $pythonw)) { $pythonw = $python }
Write-Host "Python: $python"

# --- Base compartida (config.json con la contrasena) ---
if (-not (Test-Path $INSTALL_BASE)) { New-Item -ItemType Directory -Force -Path $INSTALL_BASE | Out-Null }
$cfgFile = Join-Path $INSTALL_BASE "config.json"
if (-not (Test-Path $cfgFile)) {
    if (Test-Path "$ROOT\config.json")          { Copy-Item "$ROOT\config.json" $cfgFile }
    elseif (Test-Path "$ROOT\config.example.json") { Copy-Item "$ROOT\config.example.json" $cfgFile }
    Write-Host "AVISO: no habia config.json. Recuerda poner contrasena con configurar_password.py" -ForegroundColor Yellow
}

# --- Puerto (de config o 8080) ---
$PORT = 8080
try {
    $c = Get-Content $cfgFile -Raw | ConvertFrom-Json
    if ($c.proxy_busquedas -and $c.proxy_busquedas.puerto) { $PORT = [int]$c.proxy_busquedas.puerto }
} catch {}
Write-Host "Puerto del proxy: $PORT"

# --- 1) Dependencias (mitmproxy) ---
Write-Host "`n[1/8] Instalando mitmproxy (puede tardar)..." -ForegroundColor Cyan
& $python -m pip install --upgrade pip
& $python -m pip install -r "$MOD\requirements.txt"

$scripts  = Join-Path (Split-Path $python) "Scripts"
$mitmdump = Join-Path $scripts "mitmdump.exe"
if (-not (Test-Path $mitmdump)) { $mitmdump = (Get-Command mitmdump -ErrorAction SilentlyContinue).Source }
if (-not $mitmdump -or -not (Test-Path $mitmdump)) { throw "No se encontro mitmdump tras instalar mitmproxy." }

# --- 2) Copiar modulo a la carpeta protegida ---
Write-Host "`n[2/8] Copiando modulo a $INSTALL ..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $INSTALL | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $INSTALL "logs") | Out-Null
robocopy $MOD $INSTALL /E /XD "__pycache__" "mitmproxy" "logs" /XF "*.pyc" ".parar_proxy" | Out-Null

# --- 3) Asegurar seccion proxy_busquedas en config.json ---
Write-Host "`n[3/8] Ajustando config.json ..." -ForegroundColor Cyan
try {
    $c = Get-Content $cfgFile -Raw | ConvertFrom-Json
    if ($null -eq $c.proxy_busquedas) {
        $c | Add-Member -NotePropertyName proxy_busquedas -NotePropertyValue ([PSCustomObject]@{
            enabled = $true; puerto = $PORT; listen_host = "127.0.0.1"
        })
        ($c | ConvertTo-Json -Depth 6) | Out-File $cfgFile -Encoding utf8
        Write-Host "   - Seccion proxy_busquedas agregada."
    }
} catch { Write-Host "   (no se pudo editar config.json: $_)" -ForegroundColor Yellow }

# --- 4) Generar el certificado raiz (CA) en carpeta FIJA ---
Write-Host "`n[4/8] Generando certificado raiz local..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $CONFDIR | Out-Null
if (-not (Test-Path "$CONFDIR\mitmproxy-ca-cert.cer")) {
    $p = Start-Process -FilePath $mitmdump -ArgumentList @("-p","$PORT","--set","confdir=$CONFDIR","--set","onboarding=false") -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 6
    try { Stop-Process -Id $p.Id -Force } catch {}
    Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'mitmdump' } |
        ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force } catch {} }
}
if (-not (Test-Path "$CONFDIR\mitmproxy-ca-cert.cer")) { throw "No se genero el certificado (mitmproxy-ca-cert.cer)." }

# --- 5) Instalar el CA en el almacen de confianza de Windows ---
Write-Host "`n[5/8] Instalando el certificado en Windows (Root)..." -ForegroundColor Cyan
certutil -addstore -f Root "$CONFDIR\mitmproxy-ca-cert.cer" | Out-Null

# --- 6) Proxy del sistema -> 127.0.0.1:PORT ---
Write-Host "`n[6/8] Configurando el proxy del sistema..." -ForegroundColor Cyan
$reg = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
Set-ItemProperty -Path $reg -Name ProxyServer   -Value "127.0.0.1:$PORT"
Set-ItemProperty -Path $reg -Name ProxyOverride -Value "localhost;127.0.0.1;<local>"
Set-ItemProperty -Path $reg -Name ProxyEnable   -Value 1 -Type DWord
# Refrescar WinINET sin reiniciar el navegador
$sig = @'
[DllImport("wininet.dll", SetLastError=true)]
public static extern bool InternetSetOption(IntPtr h, int opt, IntPtr b, int len);
'@
try {
    $wi = Add-Type -MemberDefinition $sig -Name WinINetSet -Namespace FiltroBusq -PassThru
    $wi::InternetSetOption([IntPtr]::Zero, 39, [IntPtr]::Zero, 0) | Out-Null  # SETTINGS_CHANGED
    $wi::InternetSetOption([IntPtr]::Zero, 37, [IntPtr]::Zero, 0) | Out-Null  # REFRESH
} catch {}

# --- 7) Desactivar QUIC/HTTP3 (para poder inspeccionar) ---
Write-Host "`n[7/8] Desactivando QUIC/HTTP3..." -ForegroundColor Cyan
New-Item -Path "HKLM:\SOFTWARE\Policies\Google\Chrome"  -Force | Out-Null
Set-ItemProperty "HKLM:\SOFTWARE\Policies\Google\Chrome"  -Name QuicAllowed -Type DWord -Value 0
New-Item -Path "HKLM:\SOFTWARE\Policies\Microsoft\Edge"  -Force | Out-Null
Set-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Edge" -Name QuicAllowed -Type DWord -Value 0
if (-not (Get-NetFirewallRule -DisplayName "FiltroBusquedas-BlockQUIC" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "FiltroBusquedas-BlockQUIC" -Direction Outbound `
        -Protocol UDP -RemotePort 443 -Action Block | Out-Null
}

# --- Blindaje del modulo (usuario solo lectura) ---
icacls $INSTALL /inheritance:r /T | Out-Null
icacls $INSTALL /grant:r "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" "${USUARIO}:(OI)(CI)RX" /T | Out-Null

# --- 8) Tarea SYSTEM que mantiene vivo el proxy ---
Write-Host "`n[8/8] Creando tarea de arranque (SYSTEM)..." -ForegroundColor Cyan
$vig       = Join-Path $INSTALL "vigilante_proxy.py"
$action    = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$vig`""
$trigStart = New-ScheduledTaskTrigger -AtStartup
$trigLogon = New-ScheduledTaskTrigger -AtLogOn
$princ     = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName "FiltroBusquedas" -Action $action -Trigger $trigStart,$trigLogon -Principal $princ -Settings $settings -Force | Out-Null

if (Test-Path "$INSTALL\.parar_proxy") { Remove-Item "$INSTALL\.parar_proxy" -Force }
Start-ScheduledTask -TaskName "FiltroBusquedas"

Write-Host "`n=== LISTO. Capa de busquedas ACTIVA. ===" -ForegroundColor Green
Write-Host "Prueba: busca 'porn' en Google -> debe salir la pagina de bloqueo."
Write-Host "Edita el catalogo en: $MOD\listas\  y aplica con: aplicar_proxy.ps1"
Write-Host "Quitar la capa (con contrasena): desactivar_proxy.ps1"
Pause
