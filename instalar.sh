#!/usr/bin/env sh
# Instala enchufe y deja el comando `enchufe` disponible.
#
#   curl -fsSL https://raw.githubusercontent.com/leostriker111/Enchufe/main/instalar.sh | sh
#
# Nota: guardar la contrasena de la nube (--recordar) usa DPAPI, que es de
# Windows. En Linux/macOS el resto funciona, pero esa opcion no.
set -eu
REPO="https://github.com/leostriker111/Enchufe.git"

PY=""
for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1; then
        if "$c" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,9) else 1)' 2>/dev/null; then
            PY="$c"; break
        fi
    fi
done
[ -n "$PY" ] || { echo "error: hace falta Python 3.9 o mas nuevo" >&2; exit 1; }
echo "Python: $("$PY" --version 2>&1)"

if [ -f pyproject.toml ]; then "$PY" -m pip install --user --upgrade .
else "$PY" -m pip install --user --upgrade "git+$REPO"; fi

echo
if command -v enchufe >/dev/null 2>&1; then
    echo "Listo. Empieza con:  enchufe buscar"
else
    echo "Instalado. Si 'enchufe' no aparece, usa:  $PY -m enchufe"
fi
