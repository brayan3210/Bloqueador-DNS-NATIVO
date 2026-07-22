# construir_exe.ps1 - Empaqueta TODO el proyecto PC en un solo instalador .exe
# Prepara la carpeta 'payload' con todos los modulos y compila con PyInstaller.
# NO necesita administrador (compilar es a nivel de usuario).
# Resultado: instalador\dist\FiltroContenido-Setup.exe

$ErrorActionPreference = "Stop"
$INST    = Split-Path -Parent $MyInvocation.MyCommand.Definition   # ...\instalador
$ROOT    = Split-Path -Parent $INST                                 # raiz del repo
$PAYLOAD = Join-Path $INST "payload"
$python  = (Get-Command python).Source

Write-Host "=== 1) Preparando payload ===" -ForegroundColor Cyan
if (Test-Path $PAYLOAD) { Remove-Item $PAYLOAD -Recurse -Force }
New-Item -ItemType Directory -Force -Path (Join-Path $PAYLOAD "listas") | Out-Null

# Archivos de la raiz del proyecto
$rootFiles = @("filtro.py","vigilante.py","actualizar_listas.py","configurar_password.py",
    "config.example.json","requirements.txt","instalar.ps1","aplicar_cambios.ps1",
    "blindar_red.ps1","desinstalar.ps1","README.md","LICENSE")
foreach ($f in $rootFiles) { if (Test-Path "$ROOT\$f") { Copy-Item "$ROOT\$f" $PAYLOAD -Force } }
Copy-Item "$INST\TERMINOS.txt" $PAYLOAD -Force

# Listas curadas (las GRANDES descargables NO se empaquetan: instalar.ps1 las baja)
foreach ($l in @("dominios_personalizados.txt","doh_bypass.txt","ips_bloqueadas.txt","palabras_clave.txt")) {
    if (Test-Path "$ROOT\listas\$l") { Copy-Item "$ROOT\listas\$l" "$PAYLOAD\listas\" -Force }
}

# Modulo de busquedas (sin certificado/logs/temporales)
robocopy "$ROOT\proxy_busquedas" "$PAYLOAD\proxy_busquedas" /E /XD "mitmproxy" "logs" "__pycache__" /XF "*.pyc" ".parar_proxy" | Out-Null

Write-Host "=== 2) Instalando PyInstaller (si falta) ===" -ForegroundColor Cyan
& $python -m pip install --disable-pip-version-check --quiet pyinstaller

Write-Host "=== 3) Compilando el .exe ===" -ForegroundColor Cyan
# PyInstaller escribe sus logs por stderr; que eso NO aborte el script.
$ErrorActionPreference = "Continue"
Push-Location $INST
& $python -m PyInstaller --noconfirm --onefile --windowed `
    --name "FiltroContenido-Setup" `
    --add-data "payload;payload" `
    --distpath "$INST\dist" --workpath "$INST\build" --specpath "$INST" `
    "instalador.py"
$rc = $LASTEXITCODE
Pop-Location

if ($rc -eq 0 -and (Test-Path "$INST\dist\FiltroContenido-Setup.exe")) {
    Write-Host "`n=== LISTO ===" -ForegroundColor Green
    Write-Host "EXE: $INST\dist\FiltroContenido-Setup.exe"
} else {
    Write-Host "`nFALLO la compilacion (codigo $rc)" -ForegroundColor Red
}
