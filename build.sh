#!/bin/bash
# ---------------------------------------------------------------------------
# Genera "Protector de documentos.app" para Mac y un .zip listo para enviar.
#
# Uso (desde una Mac, con Python 3 instalado):
#   cd protector-documentos
#   ./build.sh
#
# El resultado aparece en la carpeta dist/:
#   dist/Protector de documentos.app
#   dist/Protector de documentos.zip   <- esto es lo que le envías a Pilar
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

NOMBRE_APP="Protector de documentos"

echo "1/4 - Preparando entorno Python..."
if [ ! -d venv ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install pyinstaller pillow -q

echo "2/4 - Generando el icono..."
python3 scripts/generar_icono.py

echo "3/4 - Limpiando compilaciones anteriores..."
rm -rf build dist "${NOMBRE_APP}.spec"

echo "4/4 - Empaquetando con PyInstaller (esto tarda uno o dos minutos)..."
pyinstaller \
  --name "$NOMBRE_APP" \
  --windowed \
  --onedir \
  --icon assets/icon.icns \
  --add-data "templates:templates" \
  --add-data "static:static" \
  --hidden-import waitress \
  --hidden-import msoffcrypto \
  --hidden-import msoffcrypto.format.ooxml \
  app.py

echo "Comprimiendo la app en un .zip para compartirla..."
cd dist
rm -f "${NOMBRE_APP}.zip"
zip -rq "${NOMBRE_APP}.zip" "${NOMBRE_APP}.app"
cd ..

echo
echo "Listo. Resultado en:"
echo "  dist/${NOMBRE_APP}.app"
echo "  dist/${NOMBRE_APP}.zip  <- envía este .zip a Pilar"
