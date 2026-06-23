# blindar_red.ps1 - Hace que el filtro funcione en CUALQUIER red/adaptador y
# cierra las vias de evasion (DoH del navegador). Se auto-eleva a administrador.
#   1) DNS 127.0.0.1 en todos los adaptadores activos.
#   2) Regla NRPT: fuerza TODO el DNS del sistema a 127.0.0.1 (independiente del
#      adaptador o la red -> cubre Wi-Fi, Ethernet, tethering, etc.).
#   3) Desactiva DoH en Edge/Chrome/Firefox por politica.
#   4) Copia las listas (incl. doh_bypass.txt) a la copia protegida y reinicia.

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell "-ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

$ErrorActionPreference = "Continue"
$SRC     = Split-Path -Parent $MyInvocation.MyCommand.Definition
$INSTALL = "C:\ProgramData\FiltroContenido"

Write-Host "=== Blindando la red ===" -ForegroundColor Cyan

# 1) DNS en todos los adaptadores activos
Write-Host "[1/4] DNS 127.0.0.1 en todos los adaptadores activos..."
Get-NetAdapter | Where-Object { $_.Status -eq "Up" } | ForEach-Object {
    Set-DnsClientServerAddress -InterfaceIndex $_.ifIndex -ServerAddresses "127.0.0.1"
    Write-Host "   - $($_.Name)"
}

# 2) NRPT: fuerza TODO el DNS a 127.0.0.1 sin importar adaptador/red
Write-Host "[2/4] Regla NRPT (cualquier red/adaptador)..."
Get-DnsClientNrptRule | Where-Object { $_.Comment -eq "FiltroContenido" } | ForEach-Object {
    Remove-DnsClientNrptRule -Name $_.Name -Force -ErrorAction SilentlyContinue
}
Add-DnsClientNrptRule -Namespace "." -NameServers "127.0.0.1" -Comment "FiltroContenido"
Write-Host "   - NRPT '.' -> 127.0.0.1 aplicada."

# 3) Desactivar DoH por politica
Write-Host "[3/4] Desactivando DoH en navegadores..."
$edge   = "HKLM:\SOFTWARE\Policies\Microsoft\Edge"
$chrome = "HKLM:\SOFTWARE\Policies\Google\Chrome"
$ffdoh  = "HKLM:\SOFTWARE\Policies\Mozilla\Firefox\DNSOverHTTPS"
New-Item -Path $edge   -Force | Out-Null
New-Item -Path $chrome -Force | Out-Null
New-Item -Path $ffdoh  -Force | Out-Null
Set-ItemProperty -Path $edge   -Name "DnsOverHttpsMode" -Value "off" -Type String
Set-ItemProperty -Path $chrome -Name "DnsOverHttpsMode" -Value "off" -Type String
Set-ItemProperty -Path $ffdoh  -Name "Enabled" -Value 0 -Type DWord
Set-ItemProperty -Path $ffdoh  -Name "Locked"  -Value 1 -Type DWord
Write-Host "   - Edge/Chrome/Firefox: DoH desactivado por politica."

# 4) Sincronizar listas (incl. doh_bypass.txt) y reiniciar el filtro
Write-Host "[4/4] Aplicando listas y reiniciando filtro..."
if (Test-Path "$INSTALL\listas") {
    Copy-Item "$SRC\listas\*" "$INSTALL\listas\" -Force
}
try { Stop-ScheduledTask -TaskName "FiltroContenido" -ErrorAction SilentlyContinue } catch {}
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'pythonw.exe' -and $_.CommandLine -match 'FiltroContenido' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
Start-ScheduledTask -TaskName "FiltroContenido"
Clear-DnsClientCache

Write-Host "`n=== Red blindada. ===" -ForegroundColor Green
Write-Host "Funciona en cualquier red/adaptador y el DoH queda bloqueado."
Write-Host "IMPORTANTE: cierra y vuelve a abrir el navegador para que tome los cambios."
Pause
