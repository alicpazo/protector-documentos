"""Genera el icono de candado de la app (assets/icon.ico y assets/icon.icns)
a partir de formas dibujadas con Pillow. No depende de ningún archivo externo.

Uso:
    python scripts/generar_icono.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

RUTA_ASSETS = Path(__file__).resolve().parent.parent / "assets"


def dibujar_candado(tamano: int) -> Image.Image:
    img = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    azul = (29, 111, 214, 255)
    azul_oscuro = (13, 63, 130, 255)
    blanco = (255, 255, 255, 255)

    margen = tamano * 0.12
    draw.rounded_rectangle(
        [margen, margen, tamano - margen, tamano - margen],
        radius=tamano * 0.22,
        fill=azul,
    )

    cx = tamano / 2
    ancho_cuerpo = tamano * 0.42
    alto_cuerpo = tamano * 0.34
    y_cuerpo = tamano * 0.52

    draw.rounded_rectangle(
        [cx - ancho_cuerpo / 2, y_cuerpo, cx + ancho_cuerpo / 2, y_cuerpo + alto_cuerpo],
        radius=tamano * 0.06,
        fill=blanco,
    )

    radio_asa = ancho_cuerpo * 0.34
    grosor_asa = tamano * 0.07
    bbox = [cx - radio_asa, y_cuerpo - radio_asa * 1.55, cx + radio_asa, y_cuerpo + radio_asa * 0.45]
    draw.arc(bbox, start=180, end=360, fill=blanco, width=int(grosor_asa))

    radio_ojo = tamano * 0.035
    cy_ojo = y_cuerpo + alto_cuerpo * 0.42
    draw.ellipse(
        [cx - radio_ojo, cy_ojo - radio_ojo, cx + radio_ojo, cy_ojo + radio_ojo],
        fill=azul_oscuro,
    )

    return img


def main():
    RUTA_ASSETS.mkdir(exist_ok=True)
    base = dibujar_candado(1024)

    tamanos_ico = [16, 24, 32, 48, 64, 128, 256]
    base.save(
        RUTA_ASSETS / "icon.ico",
        format="ICO",
        sizes=[(t, t) for t in tamanos_ico],
    )
    print(f"Creado {RUTA_ASSETS / 'icon.ico'}")

    try:
        base.save(RUTA_ASSETS / "icon.icns", format="ICNS")
        print(f"Creado {RUTA_ASSETS / 'icon.icns'}")
    except Exception as err:
        print(f"No se pudo crear icon.icns ({err}); no es necesario en Windows.")

    base.resize((512, 512)).save(RUTA_ASSETS / "icon.png")
    print(f"Creado {RUTA_ASSETS / 'icon.png'}")


if __name__ == "__main__":
    main()
