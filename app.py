"""
Protector de documentos
========================

Aplicación local (Flask) que añade contraseña real a documentos PDF y Excel.
Los documentos originales (sin proteger) se procesan siempre en memoria y
nunca se guardan en disco. El servidor solo escucha en 127.0.0.1 (localhost)
y nunca en la red.

Los documentos YA protegidos (que ya llevan su propia contraseña incluida)
se guardan en una carpeta local llamada "Documentos protegidos", en el
Escritorio, para que la persona que usa la app los encuentre fácilmente.
Nunca se guarda ninguna contraseña, ni en esa carpeta ni en los logs.
"""

import io
import json
import logging
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from protector import (
    DocumentoInvalidoError,
    proteger_excel,
    proteger_pdf,
)

# ---------------------------------------------------------------------------
# Configuración general
# ---------------------------------------------------------------------------

MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
IDLE_TIMEOUT_SECONDS = 10 * 60  # 10 minutos sin actividad -> se cierra sola
LOCK_FILENAME = "protector_documentos.lock"


def esta_empaquetado():
    """True cuando se ejecuta desde el ejecutable generado con PyInstaller."""
    return getattr(sys, "frozen", False)


def ruta_base():
    """Carpeta donde están templates/ y static/, tanto en desarrollo
    como dentro del ejecutable de PyInstaller (carpeta temporal _MEIPASS)."""
    if esta_empaquetado():
        return Path(sys._MEIPASS)  # noqa: SLF001
    return Path(__file__).resolve().parent


BASE_DIR = ruta_base()

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# Evitamos que el log de peticiones (que incluye la URL, nunca el cuerpo del
# formulario) resulte demasiado ruidoso; en ningún caso se registran
# contraseñas, porque viajan dentro del cuerpo de la petición, no en la URL.
logging.getLogger("werkzeug").setLevel(logging.WARNING)

_ultima_actividad = time.time()
_lock_actividad = threading.Lock()


@app.before_request
def _marcar_actividad():
    global _ultima_actividad
    with _lock_actividad:
        _ultima_actividad = time.time()


@app.before_request
def _bloquear_peticiones_de_otras_paginas():
    """Evita que una página web que la persona tenga abierta en otra
    pestaña pueda, sin que ella se dé cuenta, enviar peticiones a esta
    app local (por ejemplo, para cerrarla o para "proteger" algo falso).

    Solo se aplica a peticiones que cambian algo (POST). Comprobamos que
    la petición venga realmente de nuestra propia página, mirando las
    cabeceras Origin/Referer que pone el navegador."""
    if request.method != "POST":
        return

    origen_esperado = f"http://127.0.0.1:{request.environ.get('SERVER_PORT', '')}"
    origin = request.headers.get("Origin")
    referer = request.headers.get("Referer")

    if origin is not None and origin != origen_esperado:
        abort(403)
    if origin is None and referer is not None and not referer.startswith(origen_esperado + "/"):
        abort(403)


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ping")
def ping():
    """Usado para comprobar si ya hay una copia de la app abierta."""
    return jsonify({"ok": True, "pid": os.getpid()})


@app.route("/shutdown", methods=["POST"])
def shutdown():
    """La propia página avisa aquí cuando se cierra la pestaña."""
    _cerrar_servidor_en_segundo_plano()
    return jsonify({"ok": True})


def _nombre_protegido(nombre_original: str, extension: str) -> str:
    base = Path(secure_filename(nombre_original) or f"documento{extension}").stem
    if not base:
        base = "documento"
    return f"{base}-protegido{extension}"


def _respuesta_error(mensaje: str, codigo: int = 400):
    return jsonify({"ok": False, "error": mensaje}), codigo


# ---------------------------------------------------------------------------
# Carpeta "Documentos protegidos": aquí se van guardando los resultados
# (ya cifrados) para que se puedan encontrar fácilmente más tarde.
# ---------------------------------------------------------------------------

NOMBRE_CARPETA_PROTEGIDOS = "Documentos protegidos"


def _carpeta_documentos_protegidos() -> Path:
    # Usado por las pruebas automáticas para no escribir en el Escritorio real.
    override = os.environ.get("PROTECTOR_CARPETA_SALIDA")
    if override:
        carpeta = Path(override)
    else:
        escritorio = Path.home() / "Desktop"
        base = escritorio if escritorio.is_dir() else Path.home()
        carpeta = base / NOMBRE_CARPETA_PROTEGIDOS
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _ruta_disponible(carpeta: Path, nombre: str) -> Path:
    """Si "factura-protegido.pdf" ya existe, prueba
    "factura-protegido (2).pdf", "factura-protegido (3).pdf", etc."""
    ruta = carpeta / nombre
    if not ruta.exists():
        return ruta

    base = Path(nombre).stem
    extension = Path(nombre).suffix
    contador = 2
    while True:
        candidata = carpeta / f"{base} ({contador}){extension}"
        if not candidata.exists():
            return candidata
        contador += 1


def _guardar_en_carpeta_protegidos(nombre: str, datos: bytes) -> None:
    try:
        carpeta = _carpeta_documentos_protegidos()
        ruta = _ruta_disponible(carpeta, nombre)
        ruta.write_bytes(datos)
    except OSError:
        # Si no se puede escribir en la carpeta (por ejemplo, permisos),
        # no impedimos que la persona descargue igualmente su documento.
        app.logger.exception("No se pudo guardar una copia en la carpeta de documentos protegidos")


@app.route("/api/documentos")
def api_listar_documentos():
    carpeta = _carpeta_documentos_protegidos()
    documentos = []
    for ruta in carpeta.iterdir():
        if not ruta.is_file():
            continue
        extension = ruta.suffix.lower()
        if extension not in (".pdf", ".xlsx"):
            continue
        info = ruta.stat()
        documentos.append(
            {
                "nombre": ruta.name,
                "tipo": "pdf" if extension == ".pdf" else "excel",
                "fecha": datetime.fromtimestamp(info.st_mtime).isoformat(),
                "tamano": info.st_size,
            }
        )
    documentos.sort(key=lambda d: d["fecha"], reverse=True)
    return jsonify({"ok": True, "carpeta": str(carpeta), "documentos": documentos})


@app.route("/api/documentos/<nombre>")
def api_descargar_documento(nombre):
    nombre_seguro = secure_filename(nombre)
    if not nombre_seguro or nombre_seguro != nombre:
        abort(404)

    carpeta = _carpeta_documentos_protegidos()
    ruta = carpeta / nombre_seguro
    if not ruta.is_file():
        abort(404)

    return send_file(ruta, as_attachment=True, download_name=ruta.name)


@app.route("/api/abrir-carpeta", methods=["POST"])
def api_abrir_carpeta():
    carpeta = _carpeta_documentos_protegidos()
    try:
        _abrir_carpeta_en_el_explorador(carpeta)
    except Exception:
        app.logger.exception("No se pudo abrir la carpeta de documentos protegidos")
        return _respuesta_error(
            "No hemos podido abrir la carpeta. Búscala en tu Escritorio, dentro de "
            f'"{NOMBRE_CARPETA_PROTEGIDOS}".'
        )
    return jsonify({"ok": True})


def _abrir_carpeta_en_el_explorador(carpeta: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(carpeta))  # noqa: S606 - ruta generada por nosotros, no por el usuario
    elif sys.platform == "darwin":
        subprocess.run(["open", str(carpeta)], check=True)
    else:
        subprocess.run(["xdg-open", str(carpeta)], check=True)


# ---------------------------------------------------------------------------
# API: proteger PDF
# ---------------------------------------------------------------------------


@app.route("/api/proteger/pdf", methods=["POST"])
def api_proteger_pdf():
    archivo = request.files.get("documento")
    password = request.form.get("password", "")

    if archivo is None or archivo.filename == "":
        return _respuesta_error("No hemos recibido ningún documento. Elige un archivo PDF, por favor.")

    if len(password) < 4:
        return _respuesta_error("La contraseña debe tener al menos 4 caracteres.")

    nombre_original = archivo.filename
    if not nombre_original.lower().endswith(".pdf"):
        return _respuesta_error("Este archivo no es un PDF. Prueba con otro, por favor.")

    try:
        datos_entrada = archivo.read()
        salida = proteger_pdf(datos_entrada, password)
    except DocumentoInvalidoError as err:
        return _respuesta_error(str(err))
    except Exception:
        app.logger.exception("Error inesperado al proteger un PDF")
        return _respuesta_error(
            "No hemos podido proteger este documento. Inténtalo de nuevo, por favor.", 500
        )

    nombre_descarga = _nombre_protegido(nombre_original, ".pdf")
    _guardar_en_carpeta_protegidos(nombre_descarga, salida)
    return send_file(
        io.BytesIO(salida),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=nombre_descarga,
    )


# ---------------------------------------------------------------------------
# API: proteger Excel
# ---------------------------------------------------------------------------


@app.route("/api/proteger/excel", methods=["POST"])
def api_proteger_excel():
    archivo = request.files.get("documento")
    password = request.form.get("password", "")

    if archivo is None or archivo.filename == "":
        return _respuesta_error("No hemos recibido ningún documento. Elige un archivo Excel, por favor.")

    if len(password) < 4:
        return _respuesta_error("La contraseña debe tener al menos 4 caracteres.")

    nombre_original = archivo.filename
    nombre_minusculas = nombre_original.lower()

    if nombre_minusculas.endswith(".xls") or nombre_minusculas.endswith(".csv"):
        return _respuesta_error(
            "Ese tipo de archivo no se puede proteger. Solo funciona con archivos .xlsx (Excel)."
        )

    if not nombre_minusculas.endswith(".xlsx"):
        return _respuesta_error("Este archivo no es un Excel. Prueba con otro, por favor.")

    try:
        datos_entrada = archivo.read()
        salida = proteger_excel(datos_entrada, password)
    except DocumentoInvalidoError as err:
        return _respuesta_error(str(err))
    except Exception:
        app.logger.exception("Error inesperado al proteger un Excel")
        return _respuesta_error(
            "No hemos podido proteger este documento. Inténtalo de nuevo, por favor.", 500
        )

    nombre_descarga = _nombre_protegido(nombre_original, ".xlsx")
    _guardar_en_carpeta_protegidos(nombre_descarga, salida)
    return send_file(
        io.BytesIO(salida),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=nombre_descarga,
    )


@app.errorhandler(413)
def _demasiado_grande(_err):
    return _respuesta_error("Este archivo pesa demasiado. El límite es de 50 MB.", 413)


# ---------------------------------------------------------------------------
# Arranque: un único puerto libre, una única instancia, apagado automático
# ---------------------------------------------------------------------------


def _puerto_libre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _ruta_lock() -> Path:
    return Path(tempfile.gettempdir()) / LOCK_FILENAME


def _instancia_existente():
    """Si ya hay una copia de la app corriendo, devuelve su puerto."""
    ruta = _ruta_lock()
    if not ruta.exists():
        return None
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        puerto = int(datos["puerto"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None

    try:
        import urllib.request

        with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/ping", timeout=1) as resp:
            if resp.status == 200:
                return puerto
    except Exception:
        return None
    return None


def _escribir_lock(puerto: int):
    datos = {"puerto": puerto, "pid": os.getpid()}
    _ruta_lock().write_text(json.dumps(datos), encoding="utf-8")


def _borrar_lock():
    try:
        _ruta_lock().unlink(missing_ok=True)
    except OSError:
        pass


_servidor = None  # referencia al servidor werkzeug en marcha


def _cerrar_servidor_en_segundo_plano():
    def _parar():
        time.sleep(0.3)  # deja tiempo a que la respuesta HTTP salga
        _borrar_lock()
        os._exit(0)  # noqa: SLF001 - cierre limpio e inmediato del proceso

    threading.Thread(target=_parar, daemon=True).start()


def _vigilar_inactividad():
    while True:
        time.sleep(30)
        with _lock_actividad:
            inactivo = time.time() - _ultima_actividad
        if inactivo > IDLE_TIMEOUT_SECONDS:
            _borrar_lock()
            os._exit(0)  # noqa: SLF001


def _abrir_navegador_cuando_este_listo(puerto: int):
    import urllib.request

    url = f"http://127.0.0.1:{puerto}/"
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{puerto}/ping", timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)
    webbrowser.open(url)


def main():
    puerto_existente = _instancia_existente()
    if puerto_existente is not None:
        webbrowser.open(f"http://127.0.0.1:{puerto_existente}/")
        return

    puerto = _puerto_libre()
    _escribir_lock(puerto)

    threading.Thread(target=_vigilar_inactividad, daemon=True).start()
    threading.Thread(target=_abrir_navegador_cuando_este_listo, args=(puerto,), daemon=True).start()

    try:
        from waitress import serve

        serve(app, host="127.0.0.1", port=puerto)
    except ImportError:
        app.run(host="127.0.0.1", port=puerto, debug=False, use_reloader=False)
    finally:
        _borrar_lock()


if __name__ == "__main__":
    main()
