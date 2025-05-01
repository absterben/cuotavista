# bancos/scotiabank/parser.py

import fitz  # PyMuPDF
import re
import pandas as pd

def convertir_a_float(valor):
    try:
        return float(valor.replace(".", "").replace(",", "."))
    except:
        return None

def extraer_movimientos_desde_pdf(ruta_pdf):
    doc = fitz.open(ruta_pdf)
    texto_completo = "\n".join([p.get_text() for p in doc])

    # Cortar a partir de donde comienzan los movimientos
    lineas = texto_completo.split("\n")
    lineas = [l.strip() for l in lineas if l.strip()]

    for i, linea in enumerate(lineas):
        if "Escaneá los códigos de barras de tus comprobantes" in linea:
            lineas = lineas[i + 2:]
            break

    movimientos = []
    i = 0
    while i < len(lineas):
        linea = lineas[i]

        # Caso 1: movimiento con fecha
        if re.match(r"\d{2}/\d{2}/\d{2}", linea):
            fecha = linea
            detalle = lineas[i + 1] if i + 1 < len(lineas) else ""
            monto_str = lineas[i + 2] if i + 2 < len(lineas) else ""

            detalle_upper = detalle.strip().upper()

            if (
                detalle_upper == "PAGO" or
                "PAGO EN SCOTIABANK" in detalle_upper or
                "TOTAL TARJETA" in detalle_upper or
                "LEY 17934" in detalle_upper
            ):
                i += 3
                continue

            montos = re.findall(r"-?\d{1,3}(?:\.\d{3})*,\d{2}", monto_str)
            imp_pesos = convertir_a_float(montos[0]) if len(montos) >= 1 else None
            imp_usd = convertir_a_float(montos[1]) if len(montos) >= 2 else None

            movimientos.append([fecha, detalle, imp_pesos, imp_usd])
            i += 3

        # Caso 2: devolución sin fecha
        elif ("dev" in linea.lower() or "devolucion" in linea.lower()) and i + 1 < len(lineas):
            detalle = linea
            monto_str = lineas[i + 1]
            detalle_upper = detalle.strip().upper()

            if (
                detalle_upper == "PAGO" or
                "PAGO EN SCOTIABANK" in detalle_upper or
                "TOTAL TARJETA" in detalle_upper or
                "LEY 17934" in detalle_upper
            ):
                i += 2
                continue

            montos = re.findall(r"-?\d{1,3}(?:\.\d{3})*,\d{2}", monto_str)
            imp_pesos = convertir_a_float(montos[0]) if len(montos) >= 1 else None
            imp_usd = convertir_a_float(montos[1]) if len(montos) >= 2 else None

            movimientos.append(["SIN FECHA", detalle, imp_pesos, imp_usd])
            i += 2

        else:
            i += 1

    df = pd.DataFrame(movimientos, columns=[
        "Fecha", "Detalle", "Importe $", "Importe U$S"
    ])

    return df
