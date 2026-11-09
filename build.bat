@echo off
setlocal
rem ---------------------------------------------------------------------
rem Genera "Protector de documentos.exe" para Windows (un unico archivo,
rem sin ventana negra de consola).
rem
rem IMPORTANTE: este script debe ejecutarse EN WINDOWS. PyInstaller no
rem permite crear un .exe de Windows desde un Mac; necesitas un PC con
rem Windows (o una maquina virtual, o un runner de Windows en GitHub
rem Actions) con Python 3 instalado.
rem
rem Uso (desde la carpeta del proyecto, en Windows):
rem   build.bat
rem
rem El resultado aparece en la carpeta dist\:
rem   dist\Protector de documentos.exe   <- esto es lo que le envias a Pilar
rem ---------------------------------------------------------------------
cd /d "%~dp0"

set NOMBRE_APP=Protector de documentos

echo 1/4 - Preparando entorno Python...
if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install pyinstaller pillow -q

echo 2/4 - Generando el icono...
python scripts\generar_icono.py

echo 3/4 - Limpiando compilaciones anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "%NOMBRE_APP%.spec" del "%NOMBRE_APP%.spec"

echo 4/4 - Empaquetando con PyInstaller (esto tarda uno o dos minutos)...
pyinstaller ^
  --name "%NOMBRE_APP%" ^
  --onefile ^
  --noconsole ^
  --icon assets\icon.ico ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --hidden-import waitress ^
  --hidden-import msoffcrypto ^
  --hidden-import msoffcrypto.format.ooxml ^
  app.py

echo.
echo Listo. Resultado en:
echo   dist\%NOMBRE_APP%.exe
echo.
echo Envia ese archivo .exe a Pilar (por ejemplo subido a Google Drive o
echo WeTransfer, porque los .exe no se pueden adjuntar directamente en Gmail).
if not defined CI pause
