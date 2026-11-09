"""Pruebas automáticas de extremo a extremo.

Comprueban, usando el cliente de pruebas de Flask (sin arrancar un
servidor real ni abrir el navegador):

- Que un PDF normal se protege y pide la contraseña correcta al abrirlo.
- Que un Excel normal se protege con cifrado real de Office.
- Los casos límite: PDF ya protegido, extensión equivocada, contraseña
  demasiado corta, contraseñas que no coinciden (validado en el navegador,
  aquí solo backend), archivo corrupto.

Uso:
    python -m pytest tests/test_app.py -v
"""

import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import msoffcrypto
import pytest
from openpyxl import Workbook
from pypdf import PdfReader, PdfWriter

from app import app as flask_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Evita que las pruebas escriban en el Escritorio real de quien las ejecuta.
    monkeypatch.setenv("PROTECTOR_CARPETA_SALIDA", str(tmp_path / "Documentos protegidos"))
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def _pdf_de_ejemplo() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _xlsx_de_ejemplo() -> bytes:
    wb = Workbook()
    wb.active["A1"] = "hola"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_proteger_pdf_pide_password_correcta(client):
    datos = _pdf_de_ejemplo()
    resp = client.post(
        "/api/proteger/pdf",
        data={"documento": (io.BytesIO(datos), "factura.pdf"), "password": "miClave123"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.headers["Content-Disposition"].count("factura-protegido.pdf") == 1

    lector = PdfReader(io.BytesIO(resp.data))
    assert lector.is_encrypted
    assert lector.decrypt("miClave123") != 0

    lector_incorrecto = PdfReader(io.BytesIO(resp.data))
    assert lector_incorrecto.decrypt("incorrecta") == 0  # 0 = PasswordType.NOT_DECRYPTED


def test_proteger_pdf_ya_cifrado_da_error_amable(client):
    datos = _pdf_de_ejemplo()
    writer = PdfWriter(clone_from=io.BytesIO(datos))
    writer.encrypt("yaTieneClave", algorithm="AES-256")
    ya_cifrado = io.BytesIO()
    writer.write(ya_cifrado)

    resp = client.post(
        "/api/proteger/pdf",
        data={"documento": (io.BytesIO(ya_cifrado.getvalue()), "factura.pdf"), "password": "otra1234"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "ya tiene una contraseña" in resp.get_json()["error"]


def test_proteger_pdf_contrasena_corta(client):
    resp = client.post(
        "/api/proteger/pdf",
        data={"documento": (io.BytesIO(_pdf_de_ejemplo()), "factura.pdf"), "password": "abc"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "al menos 4 caracteres" in resp.get_json()["error"]


def test_proteger_pdf_archivo_no_es_pdf(client):
    resp = client.post(
        "/api/proteger/pdf",
        data={"documento": (io.BytesIO(b"no soy un pdf"), "nota.txt"), "password": "1234abcd"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "no es un PDF" in resp.get_json()["error"]


def test_proteger_pdf_archivo_corrupto(client):
    resp = client.post(
        "/api/proteger/pdf",
        data={"documento": (io.BytesIO(b"%PDF-1.4 esto esta roto"), "roto.pdf"), "password": "1234abcd"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "no hemos podido" in resp.get_json()["error"].lower()


def test_proteger_excel_pide_password_correcta(client):
    datos = _xlsx_de_ejemplo()
    resp = client.post(
        "/api/proteger/excel",
        data={"documento": (io.BytesIO(datos), "factura.xlsx"), "password": "miClave123"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.headers["Content-Disposition"].count("factura-protegido.xlsx") == 1

    archivo_office = msoffcrypto.OfficeFile(io.BytesIO(resp.data))
    assert archivo_office.is_encrypted()
    archivo_office.load_key(password="miClave123", verify_password=True)

    archivo_office_2 = msoffcrypto.OfficeFile(io.BytesIO(resp.data))
    with pytest.raises(Exception):
        archivo_office_2.load_key(password="incorrecta", verify_password=True)


def test_proteger_excel_extension_xls_rechazada(client):
    resp = client.post(
        "/api/proteger/excel",
        data={"documento": (io.BytesIO(b"contenido"), "viejo.xls"), "password": "1234abcd"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert ".xlsx" in resp.get_json()["error"]


def test_proteger_excel_extension_csv_rechazada(client):
    resp = client.post(
        "/api/proteger/excel",
        data={"documento": (io.BytesIO(b"a,b,c"), "datos.csv"), "password": "1234abcd"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert ".xlsx" in resp.get_json()["error"]


def test_proteger_excel_contrasena_corta(client):
    resp = client.post(
        "/api/proteger/excel",
        data={"documento": (io.BytesIO(_xlsx_de_ejemplo()), "factura.xlsx"), "password": "abc"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "al menos 4 caracteres" in resp.get_json()["error"]


def test_proteger_excel_archivo_corrupto(client):
    resp = client.post(
        "/api/proteger/excel",
        data={"documento": (io.BytesIO(b"esto no es un xlsx valido"), "roto.xlsx"), "password": "1234abcd"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "no hemos podido" in resp.get_json()["error"].lower()


def test_pagina_principal_carga(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Protector de documentos" in resp.get_data(as_text=True)


def test_proteger_guarda_copia_en_la_carpeta_y_aparece_listada(client):
    resp = client.post(
        "/api/proteger/pdf",
        data={"documento": (io.BytesIO(_pdf_de_ejemplo()), "factura.pdf"), "password": "miClave123"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200

    carpeta = Path(os.environ["PROTECTOR_CARPETA_SALIDA"])
    assert (carpeta / "factura-protegido.pdf").is_file()

    listado = client.get("/api/documentos").get_json()
    assert listado["ok"] is True
    nombres = [d["nombre"] for d in listado["documentos"]]
    assert "factura-protegido.pdf" in nombres
    assert listado["documentos"][0]["tipo"] == "pdf"


def test_proteger_dos_veces_el_mismo_nombre_no_sobrescribe(client):
    datos = {"documento": (io.BytesIO(_pdf_de_ejemplo()), "factura.pdf"), "password": "miClave123"}
    client.post("/api/proteger/pdf", data=datos, content_type="multipart/form-data")
    datos2 = {"documento": (io.BytesIO(_pdf_de_ejemplo()), "factura.pdf"), "password": "miClave123"}
    client.post("/api/proteger/pdf", data=datos2, content_type="multipart/form-data")

    carpeta = Path(os.environ["PROTECTOR_CARPETA_SALIDA"])
    assert (carpeta / "factura-protegido.pdf").is_file()
    assert (carpeta / "factura-protegido (2).pdf").is_file()


def test_descargar_documento_de_la_carpeta(client):
    client.post(
        "/api/proteger/excel",
        data={"documento": (io.BytesIO(_xlsx_de_ejemplo()), "factura.xlsx"), "password": "miClave123"},
        content_type="multipart/form-data",
    )
    resp = client.get("/api/documentos/factura-protegido.xlsx")
    assert resp.status_code == 200
    assert resp.headers["Content-Disposition"].count("factura-protegido.xlsx") == 1


def test_descargar_documento_fuera_de_la_carpeta_da_404(client):
    resp = client.get("/api/documentos/" + "..%2f..%2fetc%2fpasswd")
    assert resp.status_code == 404

    resp2 = client.get("/api/documentos/no-existe.pdf")
    assert resp2.status_code == 404


def test_peticion_post_con_origen_ajeno_se_bloquea(client):
    resp = client.post(
        "/api/proteger/pdf",
        data={"documento": (io.BytesIO(_pdf_de_ejemplo()), "factura.pdf"), "password": "miClave123"},
        content_type="multipart/form-data",
        headers={"Origin": "https://pagina-maliciosa.example"},
    )
    assert resp.status_code == 403


def test_peticion_post_con_mismo_origen_funciona(client):
    resp = client.post(
        "/api/proteger/pdf",
        data={"documento": (io.BytesIO(_pdf_de_ejemplo()), "factura.pdf"), "password": "miClave123"},
        content_type="multipart/form-data",
        headers={"Origin": "http://127.0.0.1:12345"},
        base_url="http://127.0.0.1:12345",
    )
    assert resp.status_code == 200


def test_abrir_carpeta_responde_ok(client, monkeypatch):
    import app as app_module

    llamadas = []
    monkeypatch.setattr(app_module, "_abrir_carpeta_en_el_explorador", lambda carpeta: llamadas.append(carpeta))

    resp = client.post("/api/abrir-carpeta")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    assert len(llamadas) == 1
