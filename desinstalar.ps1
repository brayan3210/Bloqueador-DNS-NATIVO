# desinstalar.ps1 - Desactiva y elimina el filtro. REQUIERE LA CONTRASENA.
# Quita el blindaje, restaura el DNS, detiene todo y borra la copia protegida.
# Se auto-eleva a administrador.

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell "-ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

$ErrorActionPreference = "Continue"
$INSTALL = "C:\ProgramData\FiltroContenido"
$SRC     = Split-Path -Parent $MyInvocation.MyCommand.Definition

# La contrasena se lee de la copia protegida si existe; si no, de la del Escritorio.
$cfgPath = if (Test-Path "$INSTALL\config.json") { "$INSTALL\config.json" } else { "$SRC\config.json" }
$config  = Get-Content $cfgPath -Raw | ConvertFrom-Json

# --- Verificar contrasena ---
$guardado = $config.password_hash
if ([string]::IsNullOrEmpty($guardado)) {
    Write-Host "AVISO: no hay contrasena configurada. Se permite desinstalar." -ForegroundColor Yellow
} else {
    $pw = Read-Host "Contrasena para desactivar el filtro" -AsSecureString
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
if (Test-Path $INSTALL) { New-Item -ItemType File -Path "$INSTALL\.parar" -Force | Out-Null }

# --- Detener tarea y procesos ---
Write-Host "Deteniendo filtro..."
try { Stop-ScheduledTask -TaskName "FiltroContenido" } catch {}
try { Unregister-ScheduledTask -TaskName "FiltroContenido" -Confirm:$false } catch {}
Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match "filtro.py" -or $_.CommandLine -match "vigilante.py"
} | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force } catch {} }

# --- Restaurar DNS ---
Write-Host "Restaurando DNS..."
$bk = if (Test-Path "$INSTALL\dns_backup.json") { "$INSTALL\dns_backup.json" } else { "$SRC\dns_backup.json" }
if (Test-Path $bk) {
    $backup = Get-Content $bk -Raw | ConvertFrom-Json
    foreach ($b in $backup) {
        if ($b.servers -and $b.servers.Count -gt 0) {
            Set-DnsClientServerAddress -InterfaceIndex $b.ifIndex -ServerAddresses $b.servers
        } else {
            Set-DnsClientServerAddress -InterfaceIndex $b.ifIndex -ResetServerAddresses
        }
    }
} else {
    Get-NetAdapter | Where-Object { $_.Status -eq "Up" } | ForEach-Object {
        Set-DnsClientServerAddress -InterfaceIndex $_.ifIndex -ResetServerAddresses
    }
}
Clear-DnsClientCache

# --- Revertir blindaje de red (NRPT + DoH) ---
Write-Host "Revirtiendo NRPT y DoH..."
Get-DnsClientNrptRule | Where-Object { $_.Comment -eq "FiltroContenido" } | ForEach-Object {
    Remove-DnsClientNrptRule -Name $_.Name -Force -ErrorAction SilentlyContinue
}
Remove-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Edge"  -Name "DnsOverHttpsMode" -ErrorAction SilentlyContinue
Remove-ItemProperty "HKLM:\SOFTWARE\Policies\Google\Chrome"   -Name "DnsOverHttpsMode" -ErrorAction SilentlyContinue
Remove-Item "HKLM:\SOFTWARE\Policies\Mozilla\Firefox\DNSOverHTTPS" -Recurse -ErrorAction SilentlyContinue

# --- Quitar blindaje y borrar copia protegida ---
if (Test-Path $INSTALL) {
    Write-Host "Quitando blindaje y borrando $INSTALL ..."
    Start-Sleep -Seconds 2
    takeown /F $INSTALL /R /D Y | Out-Null
    icacls $INSTALL /reset /T | Out-Null
    attrib -h $INSTALL
    Remove-Item $INSTALL -Recurse -Force
}

Write-Host "`nFiltro desinstalado. DNS restaurado." -ForegroundColor Green
Pause
