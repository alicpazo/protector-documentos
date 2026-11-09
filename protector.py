"""
Lógica de cifrado de documentos.

Todo ocurre en memoria: recibimos los bytes del archivo original y
devolvemos los bytes del archivo ya protegido, sin tocar el disco
(salvo el archivo temporal que msoffcrypto necesita internamente para
leer el .xlsx, que se borra en cuanto terminamos).
"""

import io

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError, FileNotDecryptedError

import msoffcrypto
from msoffcrypto.exceptions import DecryptionError


class DocumentoInvalidoError(Exception):
    """Error pensado para mostrarse directamente a Pilar, en español
    sencillo, explicando qué ha pasado y qué puede hacer."""


def proteger_pdf(datos_entrada: bytes, password: str) -> bytes:
    entrada = io.BytesIO(datos_entrada)

    try:
        lector = PdfReader(entrada)
    except Exception as err:
        raise DocumentoInvalidoError(
            "No hemos podido abrir este documento. Puede estar dañado. Prueba con otro, por favor."
        ) from err

    if lector.is_encrypted:
        raise DocumentoInvalidoError(
            "Este PDF ya tiene una contraseña puesta. Quítasela primero y vuelve a intentarlo."
        )

    try:
        # Al menos una página, para detectar PDFs corruptos cuanto antes.
        _ = len(lector.pages)
        entrada.seek(0)
        escritor = PdfWriter(clone_from=entrada)
        escritor.encrypt(password, algorithm="AES-256")

        salida = io.BytesIO()
        escritor.write(salida)
        return salida.getvalue()
    except (PdfReadError, FileNotDecryptedError) as err:
        raise DocumentoInvalidoError(
            "No hemos podido abrir este documento. Puede estar dañado. Prueba con otro, por favor."
        ) from err
    except Exception as err:
        raise DocumentoInvalidoError(
            "No hemos podido proteger este documento. Inténtalo de nuevo, por favor."
        ) from err


def proteger_excel(datos_entrada: bytes, password: str) -> bytes:
    entrada = io.BytesIO(datos_entrada)

    try:
        archivo_office = msoffcrypto.OfficeFile(entrada)
    except Exception as err:
        raise DocumentoInvalidoError(
            "No hemos podido abrir este documento. Puede estar dañado. Prueba con otro, por favor."
        ) from err

    try:
        ya_protegido = archivo_office.is_encrypted()
    except Exception:
        ya_protegido = False

    if ya_protegido:
        raise DocumentoInvalidoError(
            "Este Excel ya tiene una contraseña puesta. Quítasela primero y vuelve a intentarlo."
        )

    salida = io.BytesIO()
    try:
        archivo_office.encrypt(password, salida)
    except DecryptionError as err:
        raise DocumentoInvalidoError(
            "No hemos podido proteger este documento. Inténtalo de nuevo, por favor."
        ) from err
    except Exception as err:
        raise DocumentoInvalidoError(
            "No hemos podido abrir este documento. Puede estar dañado. Prueba con otro, por favor."
        ) from err

    return salida.getvalue()
