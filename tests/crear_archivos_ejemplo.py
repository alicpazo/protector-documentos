"""Crea archivos de ejemplo (PDF y Excel) para probar la app manualmente.

Uso:
    python tests/crear_archivos_ejemplo.py
Genera tests/ejemplos/factura.pdf y tests/ejemplos/factura.xlsx
"""

from pathlib import Path

from openpyxl import Workbook
from pypdf import PdfWriter

CARPETA = Path(__file__).resolve().parent / "ejemplos"


def crear_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    ruta = CARPETA / "factura.pdf"
    with open(ruta, "wb") as f:
        writer.write(f)
    print(f"Creado {ruta}")


def crear_xlsx():
    wb = Workbook()
    ws = wb.active
    ws.title = "Factura"
    ws["A1"] = "Cliente"
    ws["B1"] = "Importe"
    ws["A2"] = "Pilar"
    ws["B2"] = 123.45
    ruta = CARPETA / "factura.xlsx"
    wb.save(ruta)
    print(f"Creado {ruta}")


if __name__ == "__main__":
    CARPETA.mkdir(exist_ok=True)
    crear_pdf()
    crear_xlsx()
