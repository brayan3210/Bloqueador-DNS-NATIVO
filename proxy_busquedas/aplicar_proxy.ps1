# aplicar_proxy.ps1 - Aplica los cambios del catalogo/excepciones a la copia
# protegida y reinicia el proxy de busquedas. Usalo cada vez que edites
# listas\catalogo_busqueda.txt o listas\excepciones_educativas.txt.
# Se auto-eleva a administrador.

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell "-ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

$ErrorActionPreference = "Stop"
$MOD     = Split-Path -Parent $MyInvocation.MyCommand.Definition
$INSTALL = "C:\ProgramData\FiltroContenido\proxy_busquedas"

if (-not (Test-Path $INSTALL)) {
    Write-Host "La capa de busquedas no esta instalada. Ejecuta instalar_proxy.ps1 primero." -ForegroundColor Red
    Pause; exit
}

Write-Host "Aplicando catalogo/excepciones y codigo a la copia protegida..." -ForegroundColor Cyan
Copy-Item "$MOD\listas\catalogo_busqueda.txt"      "$INSTALL\listas\" -Force
Copy-Item "$MOD\listas\excepciones_educativas.txt" "$INSTALL\listas\" -Force
Copy-Item "$MOD\motor_busqueda.py" "$INSTALL\motor_busqueda.py" -Force
Copy-Item "$MOD\addon_proxy.py"    "$INSTALL\addon_proxy.py"    -Force
Copy-Item "$MOD\iniciar_proxy.py"  "$INSTALL\iniciar_proxy.py"  -Force
Copy-Item "$MOD\vigilante_proxy.py" "$INSTALL\vigilante_proxy.py" -Force
Copy-Item "$MOD\bloqueo.html"      "$INSTALL\bloqueo.html"      -Force

Write-Host "Reiniciando el proxy de busquedas..." -ForegroundColor Cyan
try { Stop-ScheduledTask -TaskName "FiltroBusquedas" -ErrorAction SilentlyContinue } catch {}
Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match "vigilante_proxy.py" -or $_.CommandLine -match "iniciar_proxy.py" -or $_.CommandLine -match "mitmdump"
} | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {} }
Start-Sleep -Seconds 2
Start-ScheduledTask -TaskName "FiltroBusquedas"
Start-Sleep -Seconds 2

$n = (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'mitmdump' }).Count
Write-Host "Cambios aplicados. Procesos mitmdump activos: $n" -ForegroundColor Green
Pause
