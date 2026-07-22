# desactivar_proxy.ps1 - Quita la capa de bloqueo de BUSQUEDAS. REQUIERE CONTRASENA.
# Detiene el proxy, quita el proxy del sistema, borra el certificado, reactiva
# QUIC y elimina la tarea. NO toca el filtro DNS. Se auto-eleva a administrador.

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell "-ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

$ErrorActionPreference = "Continue"
$MOD          = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ROOT         = Split-Path -Parent $MOD
$INSTALL_BASE = "C:\ProgramData\FiltroContenido"
$INSTALL      = Join-Path $INSTALL_BASE "proxy_busquedas"

# La contrasena se lee de la copia protegida si existe; si no, del repo.
$cfgPath = if (Test-Path "$INSTALL_BASE\config.json") { "$INSTALL_BASE\config.json" } else { "$ROOT\config.json" }
$config  = $null
if (Test-Path $cfgPath) { $config = Get-Content $cfgPath -Raw | ConvertFrom-Json }

# --- Verificar contrasena (igual que desinstalar.ps1) ---
$guardado = if ($config) { $config.password_hash } else { $null }
if ([string]::IsNullOrEmpty($guardado)) {
    Write-Host "AVISO: no hay contrasena configurada. Se permite desactivar." -ForegroundColor Yellow
} else {
    $pw = Read-Host "Contrasena para desactivar la capa de busquedas" -AsSecureString
    $bstr  = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($pw)
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    $bytes = [Text.Encoding]::UTF8.GetBytes($plain)
    $stream = [IO.MemoryStream]::new($bytes)
    $hash  = (Get-FileHash -InputStream $stream -Algorithm SHA256).Hash.ToLower()
    if ($hash -ne $guardado.ToLower()) {
        Write-Host "Contrasena incorrecta. No se desactivo nada." -ForegroundColor Red
        Pause; exit
    }
    Write-Host "Contrasena correcta." -ForegroundColor Green
}

# --- Senal de parada para el vigilante ---
if (Test-Path $INSTALL) { New-Item -ItemType File -Path "$INSTALL\.parar_proxy" -Force | Out-Null }

# --- Detener tarea y procesos ---
Write-Host "Deteniendo el proxy de busquedas..."
try { Stop-ScheduledTask -TaskName "FiltroBusquedas" } catch {}
try { Unregister-ScheduledTask -TaskName "FiltroBusquedas" -Confirm:$false } catch {}
Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match "vigilante_proxy.py" -or $_.CommandLine -match "iniciar_proxy.py" -or $_.CommandLine -match "mitmdump"
} | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force } catch {} }

# --- Quitar el proxy del sistema ---
Write-Host "Quitando el proxy del sistema..."
$reg = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
Set-ItemProperty -Path $reg -Name ProxyEnable -Value 0 -Type DWord
Remove-ItemProperty -Path $reg -Name ProxyServer -ErrorAction SilentlyContinue
$sig = @'
[DllImport("wininet.dll", SetLastError=true)]
public static extern bool InternetSetOption(IntPtr h, int opt, IntPtr b, int len);
'@
try {
    $wi = Add-Type -MemberDefinition $sig -Name WinINetDel -Namespace FiltroBusq -PassThru
    $wi::InternetSetOption([IntPtr]::Zero, 39, [IntPtr]::Zero, 0) | Out-Null
    $wi::InternetSetOption([IntPtr]::Zero, 37, [IntPtr]::Zero, 0) | Out-Null
} catch {}

# --- Reactivar QUIC ---
Write-Host "Reactivando QUIC/HTTP3..."
Remove-ItemProperty "HKLM:\SOFTWARE\Policies\Google\Chrome"  -Name QuicAllowed -ErrorAction SilentlyContinue
Remove-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Edge" -Name QuicAllowed -ErrorAction SilentlyContinue
Get-NetFirewallRule -DisplayName "FiltroBusquedas-BlockQUIC" -ErrorAction SilentlyContinue |
    Remove-NetFirewallRule -ErrorAction SilentlyContinue

# --- Borrar el certificado raiz ---
Write-Host "Borrando el certificado raiz (mitmproxy)..."
certutil -delstore Root "mitmproxy" | Out-Null

# --- Borrar el modulo protegido ---
if (Test-Path $INSTALL) {
    Write-Host "Quitando blindaje y borrando $INSTALL ..."
    Start-Sleep -Seconds 2
    takeown /F $INSTALL /R /D Y | Out-Null
    icacls $INSTALL /reset /T | Out-Null
    Remove-Item $INSTALL -Recurse -Force
}

Write-Host "`nCapa de busquedas desactivada. (El filtro DNS sigue intacto.)" -ForegroundColor Green
Pause
