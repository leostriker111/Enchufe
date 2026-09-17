<#
    Instala enchufe y deja el comando `enchufe` disponible.

        irm https://raw.githubusercontent.com/leostriker111/Enchufe/main/instalar.ps1 | iex

    O, desde una copia del repositorio:  .\instalar.ps1
#>
$ErrorActionPreference = "Stop"
$REPO = "https://github.com/leostriker111/Enchufe.git"

$py = $null
foreach ($c in @("python", "python3", "py")) {
    if (Get-Command $c -ErrorAction SilentlyContinue) {
        & $c -c "import sys; raise SystemExit(0 if sys.version_info >= (3,9) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { $py = $c; break }
    }
}
if (-not $py) { Write-Host "error: hace falta Python 3.9 o mas nuevo" -ForegroundColor Red; exit 1 }
Write-Host "Python: $(& $py --version 2>&1)"

if (Test-Path "pyproject.toml") { & $py -m pip install --user --upgrade . }
else { & $py -m pip install --user --upgrade "git+$REPO" }
if ($LASTEXITCODE -ne 0) { Write-Host "error: fallo la instalacion" -ForegroundColor Red; exit 1 }

Write-Host ""
if (Get-Command enchufe -ErrorAction SilentlyContinue) {
    Write-Host "Listo. Empieza con:  enchufe buscar" -ForegroundColor Green
} else {
    Write-Host "Instalado. Si 'enchufe' no aparece, usa:  $py -m enchufe"
    Write-Host "o agrega a tu PATH la carpeta Scripts de tu Python de usuario."
}
