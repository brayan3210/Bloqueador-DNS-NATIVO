# aplicar_cambios.ps1 - Copia las listas que editaste en el Escritorio a la
# carpeta protegida y reinicia el filtro. Usalo cada vez que agregues
# palabras/dominios/IPs. Se auto-eleva a administrador.

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell "-ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

$ErrorActionPreference = "Stop"
$SRC     = Split-Path -Parent $MyInvocation.MyCommand.Definition
$INSTALL = "C:\ProgramData\FiltroContenido"

if (-not (Test-Path $INSTALL)) {
    Write-Host "El filtro no esta instalado. Ejecuta instalar.ps1 primero." -ForegroundColor Red
    Pause; exit
}

Write-Host "Aplicando tus listas del Escritorio a la copia protegida..." -ForegroundColor Cyan
Copy-Item "$SRC\listas\palabras_clave.txt"        "$INSTALL\listas\" -Force
Copy-Item "$SRC\listas\dominios_personalizados.txt" "$INSTALL\listas\" -Force
Copy-Item "$SRC\listas\ips_bloqueadas.txt"         "$INSTALL\listas\" -Force
# Sincroniza config.json (por si cambiaste la contrasena) y el codigo del programa.
Copy-Item "$SRC\config.json"          "$INSTALL\config.json" -Force
Copy-Item "$SRC\filtro.py"            "$INSTALL\filtro.py" -Force
Copy-Item "$SRC\vigilante.py"         "$INSTALL\vigilante.py" -Force
Copy-Item "$SRC\actualizar_listas.py" "$INSTALL\actualizar_listas.py" -Force

Write-Host "Reiniciando el filtro (forzado)..." -ForegroundColor Cyan
try { Stop-ScheduledTask -TaskName "FiltroContenido" -ErrorAction SilentlyContinue } catch {}
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'pythonw.exe' -and $_.CommandLine -match 'FiltroContenido' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
Start-ScheduledTask -TaskName "FiltroContenido"
Start-Sleep -Seconds 3
Clear-DnsClientCache
$n = (Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'pythonw.exe' -and $_.CommandLine -match 'FiltroContenido' }).Count
Write-Host "Cambios aplicados. Procesos del filtro activos: $n" -ForegroundColor Green

# Reporte de estado (para confirmar persistencia tras reinicio)
$rep = "$SRC\estado.txt"
"=== Estado $(Get-Date) ===" | Out-File $rep -Encoding utf8
"Procesos del filtro activos: $n" | Out-File $rep -Append -Encoding utf8
"--- Disparadores de la tarea (debe aparecer MSFT_TaskBootTrigger = al arrancar Windows) ---" | Out-File $rep -Append -Encoding utf8
try {
    $t = Get-ScheduledTask -TaskName "FiltroContenido"
    ($t.Triggers | ForEach-Object { $_.CimClass.CimClassName }) -join ", " | Out-File $rep -Append -Encoding utf8
    "Estado de la tarea: $($t.State)" | Out-File $rep -Append -Encoding utf8
} catch { "No se pudo leer la tarea: $_" | Out-File $rep -Append -Encoding utf8 }
Pause
