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

    if inicio != -1 and fin != -1 and fin > inicio:
        texto_movimientos = texto_completo[inicio:fin]
    elif inicio != -1:
        texto_movimientos = texto_completo[inicio:]
    else:
        texto_movimientos = texto_completo

    lineas = texto_movimientos.strip().split("\n")
    movimientos = []

    i = 0
    while i < len(lineas):
        original_line = lineas[i].strip()

        if not original_line or any(p in original_line.upper() for p in [
            "SALDO DEL ESTADO", "SALDO CONTADO", "PAGOS", "MILLAS"
        ]):
            i += 1
            continue

        if "REDUCCIÓN DE IVA" in original_line.upper():
            i += 1
            continue

        if re.fullmatch(r"[%\d\s\.,-]*", original_line) and not re.search(r"[A-Za-z]", original_line):
            i += 1
            continue

        montos = re.findall(r"-?(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}", original_line)
        texto_limpio = re.sub(r"\d{1,3}(?:\.\d{3})*,\d{2}", "", original_line).strip()

        fecha_match = re.match(r"(\d{2} \d{2} \d{2})", texto_limpio)
        fecha = fecha_match.group(1) if fecha_match else ""
        resto = texto_limpio[len(fecha):].strip() if fecha else texto_limpio

        tarjeta_match = re.match(r"(\d{4})", resto)
        tarjeta = tarjeta_match.group(1) if tarjeta_match else ""
        detalle = resto[len(tarjeta):].strip() if tarjeta else resto

        excepciones_validas = [
            "SEGURO DE VIDA", 
            "INTERESES COMPENSATORIOS", 
            "INTERESES MORATORIOS"
        ]

        # ❌ Si no hay contenido útil
        if not fecha and not tarjeta and not re.search(r"[A-Za-z]", detalle):
            i += 1
            continue

        if not fecha and not tarjeta and all(p not in detalle.upper() for p in excepciones_validas):
            i += 1
            continue

        # ⚠️ Si no hay montos y es una excepción, mirar la próxima línea
        if not montos and any(p in detalle.upper() for p in excepciones_validas):
            if i + 1 < len(lineas):
                siguiente = lineas[i + 1]
                montos = re.findall(r"-?(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}", siguiente)
                i += 1  # saltamos la línea siguiente porque ya la usamos

        imp_origen, imp_pesos, imp_usd = None, None, None
        if any(p in detalle.upper() for p in excepciones_validas):
            if len(montos) == 2:
                imp_pesos = convertir_a_float(montos[0])
                imp_usd = convertir_a_float(montos[1])
            elif len(montos) == 1:
                imp_pesos = convertir_a_float(montos[0])
        elif len(montos) == 2:
            imp_origen = convertir_a_float(montos[0])
            imp_usd = convertir_a_float(montos[1])
        elif len(montos) == 1:
            imp_pesos = convertir_a_float(montos[0])

        movimientos.append([fecha, tarjeta, detalle, imp_origen, imp_pesos, imp_usd])
        i += 1

    df = pd.DataFrame(movimientos, columns=[
        "Fecha", "Tarjeta", "Detalle", "Importe origen", "Importe $", "Importe U$S"
    ])

    return df
