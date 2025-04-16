# bancos/itau/parser.py

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

    inicio = texto_completo.find("SALDO DEL ESTADO DE CUENTA ANTERIOR")
    fin = texto_completo.find("UD. HA GENERADO")
    texto_movimientos = texto_completo[inicio:fin] if inicio != -1 and fin != -1 else ""

    lineas = texto_movimientos.strip().split("\n")
    movimientos = []

    for linea in lineas:
        linea = linea.strip()

        if not linea or any(p in linea.upper() for p in [
            "SALDO DEL ESTADO", "SALDO CONTADO", "PAGOS", "MILLAS", "INTERESES", "MORA"
        ]):
            continue

        montos = re.findall(r"-?(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}", linea)
        texto_limpio = re.sub(r"\d{1,3}(?:\.\d{3})*,\d{2}", "", linea).strip()

        fecha_match = re.match(r"(\d{2} \d{2} \d{2})", texto_limpio)
        fecha = fecha_match.group(1) if fecha_match else ""
        resto = texto_limpio[len(fecha):].strip() if fecha else texto_limpio

        tarjeta_match = re.match(r"(\d{4})", resto)
        tarjeta = tarjeta_match.group(1) if tarjeta_match else ""
        detalle = resto[len(tarjeta):].strip() if tarjeta else resto

        imp_origen, imp_pesos, imp_usd = None, None, None
        if "SEGURO DE VIDA" in detalle.upper() and len(montos) == 2:
            imp_pesos = convertir_a_float(montos[0])
            imp_usd = convertir_a_float(montos[1])
        elif len(montos) == 2:
            imp_origen = convertir_a_float(montos[0])
            imp_usd = convertir_a_float(montos[1])
        elif len(montos) == 1:
            imp_pesos = convertir_a_float(montos[0])

        movimientos.append([fecha, tarjeta, detalle, imp_origen, imp_pesos, imp_usd])

    df = pd.DataFrame(movimientos, columns=[
        "Fecha", "Tarjeta", "Detalle", "Importe origen", "Importe $", "Importe U$S"
    ])

    return df
