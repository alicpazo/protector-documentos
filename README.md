# Protector de documentos

App local (Flask) para añadir contraseña real a archivos PDF (AES-256, vía
`pypdf`) y Excel .xlsx (cifrado real de Office, vía `msoffcrypto-tool`). El
documento original (sin proteger) se procesa siempre en memoria; el servidor
solo escucha en `127.0.0.1` y nunca se registran contraseñas. Los documentos
YA protegidos se guardan también en una carpeta "Documentos protegidos" en
el Escritorio, para que se encuentren fácilmente más tarde.

## Estructura del proyecto

```
app.py                  Servidor Flask: rutas, instancia única, apagado automático
protector.py             Lógica de cifrado (PDF y Excel), con mensajes de error en español
templates/index.html     La única pantalla de la app
static/css/style.css     Estilos (letra grande, alto contraste, sin modo oscuro)
static/js/app.js         Arrastrar y soltar, mostrar/ocultar contraseña, descarga automática
assets/                  Icono de la app (icon.ico para Windows, icon.icns para Mac)
scripts/generar_icono.py Genera los iconos (no depende de archivos externos)
tests/                   Pruebas automáticas + generador de archivos de ejemplo
build.sh / build.bat     Scripts de empaquetado con PyInstaller
.github/workflows/       Flujo de GitHub Actions para generar el .exe sin tener Windows
```

## Probar en modo desarrollo (con Python instalado)

```bash
python3 -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 app.py
```

Se abrirá sola una pestaña del navegador en `http://127.0.0.1:<puerto libre>/`.

## Pruebas automáticas

```bash
pip install pytest openpyxl
python3 -m pytest tests/test_app.py -v
```

Las 11 pruebas comprueban, entre otras cosas, que los PDF y Excel resultantes
quedan realmente cifrados (se abren con `pypdf` / `msoffcrypto-tool` usando
la contraseña correcta, y se rechazan con una incorrecta) y todos los casos
límite del encargo (PDF ya protegido, extensión equivocada, contraseña
corta, archivo corrupto).

Para generar archivos de ejemplo con los que probar la app a mano:

```bash
python3 tests/crear_archivos_ejemplo.py
```

Esto crea `tests/ejemplos/factura.pdf` y `tests/ejemplos/factura.xlsx`.

## Empaquetar la app

### Mac (`.app` + `.zip`)

Desde una Mac, con Python 3 instalado:

```bash
./build.sh
```

Genera `dist/Protector de documentos.app` y `dist/Protector de documentos.zip`
(este último es el que le envías a quien vaya a usarlo).

### Windows (`.exe`)

**Importante:** PyInstaller no permite "cross-compilar" — genera ejecutables
para el sistema operativo en el que se ejecuta. Como Mac no puede generar un
`.exe` de Windows directamente, tienes dos opciones:

**Opción A — Con un PC/VM Windows:**
Copia la carpeta del proyecto a un ordenador (o máquina virtual) con Windows
y Python 3 instalados, y ejecuta:

```bat
build.bat
```

Genera `dist\Protector de documentos.exe` (un único archivo, sin consola).

**Opción B — Sin tener Windows, usando GitHub Actions (recomendado):**
1. Sube este proyecto a un repositorio de GitHub (puede ser privado).
2. Ve a la pestaña **Actions** del repositorio.
3. Entra en "Generar ejecutable de Windows" → **Run workflow**.
4. Espera 2-3 minutos y descarga el `.exe` desde la sección **Artifacts**
   de esa ejecución.

El flujo ya está configurado en `.github/workflows/build-windows.yml`: pide
prestado un ordenador Windows a GitHub, ejecuta `build.bat` en él y te deja
el `.exe` listo para descargar, sin que tú necesites tener Windows.

## Qué hace la app al abrirse (en ambos sistemas)

- Busca un puerto libre en `127.0.0.1` y arranca el servidor ahí.
- Abre sola una pestaña del navegador apuntando a ese puerto.
- Si ya había una copia abierta, no arranca una segunda: simplemente
  reabre la pestaña de la que ya estaba corriendo.
- Al cerrar la pestaña del navegador (o tras 10 minutos sin usarla), el
  programa se cierra solo.
- Cada documento protegido se guarda también en `~/Desktop/Documentos
  protegidos` (configurable con la variable de entorno
  `PROTECTOR_CARPETA_SALIDA`, usada por las pruebas automáticas).
- Las peticiones que cambian algo (proteger, abrir carpeta, cerrar la app)
  comprueban la cabecera `Origin`/`Referer` del navegador, para que una
  página web distinta que la persona tenga abierta en otra pestaña no
  pueda darle órdenes a esta app sin que ella lo sepa.

## Comprobaciones ya realizadas

Antes de entregar el proyecto se comprobó, con pruebas automáticas y
pruebas manuales ejecutando el ejecutable empaquetado de Mac:

- El PDF resultante pide contraseña al abrirlo (verificado con `pypdf`,
  comprobando que la contraseña correcta funciona y una incorrecta no).
- El Excel resultante pide contraseña al abrirlo con Excel real
  (verificado con `msoffcrypto-tool`, igual que arriba).
- La app empaquetada con PyInstaller sirve correctamente la página y
  ambos formularios, con las plantillas y estilos ya incluidos dentro
  del ejecutable.
- La detección de "instancia única" y el apagado al cerrar la pestaña
  (`/shutdown`) funcionan correctamente.
- Los 18 casos de prueba automáticos (`tests/test_app.py`) pasan, incluidos
  todos los casos límite del encargo original, el guardado en la carpeta
  "Documentos protegidos" (sin sobrescribir archivos con el mismo nombre),
  la protección contra acceder a archivos fuera de esa carpeta, y el
  bloqueo de peticiones que no vienen de la propia página.

**Pendiente de verificar por tu parte:** el `.exe` de Windows en un PC
Windows real (idealmente el de Pilar, o uno similar), ya que no se puede
generar ni ejecutar un `.exe` de Windows desde este Mac. El código es el
mismo en ambos sistemas, así que el comportamiento debería ser idéntico.
