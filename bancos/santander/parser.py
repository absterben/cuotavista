# bancos/santander/parser.py

"""
Parser para PDFs de Santander.
Extrae movimientos del estado de cuenta, manejando PDFs encriptados.

REGLAS DE PARSING (v2 - fail-safe):
- Solo captura movimientos que cumplan el patrón fuerte:
  fecha (dd/mm/yyyy) + tarjeta (3 dígitos) + detalle (con letras) + importe
- Blacklist estricta para excluir líneas de resumen/metadata
- Si una línea no cumple el patrón exacto, se descarta
"""

from pypdf import PdfReader
from io import BytesIO
import pandas as pd
import re


# ============================================================================
# BLACKLIST: Palabras que indican líneas de resumen/metadata (NO transacciones)
# ============================================================================
BLACKLIST_PALABRAS = [
    "SALDO ANTERIOR",
    "SALDO CONTADO", 
    "PAGO TOTAL",
    "PAGO MINIMO",
    "P.MINIMO",
    "P.CONTADO",
    "LIMITE",
    "LÍMITE",
    "CREDITO DISPONIBLE",
    "CRÉDITO DISPONIBLE",
    "VENCIMIENTO",
    "CIERRE",
    "TASA",
    "CUOTAS A VENCER",
    "RESUMEN",
    "TOTAL DEV LEY",
    "IMPORTE TOTAL",
    "ESTADO DE CUENTA",
    "TARJETA DE CREDITO",
    "TARJETA DE CRÉDITO",
    "PAGINA",
    "PÁGINA",
    "TITULAR",
    "NUMERO DE CUENTA",
    "NÚMERO DE CUENTA",
]

# Patrón FUERTE para transacciones válidas:
# fecha (dd/mm/yyyy) + espacio + tarjeta (3 dígitos) + espacio + detalle + espacio + importe
PATRON_TRANSACCION_FUERTE = re.compile(
    r'^(\d{2}/\d{2}/\d{4})\s+'    # Fecha dd/mm/yyyy + espacio obligatorio
    r'(\d{3})\s+'                  # Tarjeta exactamente 3 dígitos + espacio
    r'(.+?)\s+'                    # Detalle (captura mínima)
    r'([\d]{1,3}(?:\.[\d]{3})*,[\d]{2}-?)\s*$'  # Importe formato uruguayo
)

# Patrón para detectar líneas corruptas (fecha pegada a números largos)
PATRON_FECHA_CORRUPTA = re.compile(
    r'^\d{2}/\d{2}/\d{4}\d+'       # Fecha seguida inmediatamente de más dígitos
)

# Whitelist de conceptos válidos (permitidos incluso sin tarjeta)
CONCEPTOS_VALIDOS = [
    'MULTA POR MORA',
    'LEY 18212',
    'INTERESES FINANCIEROS',
    'I.V.A',
    'IVA',
    'IVA 22%',
]

# Patrón controlado para conceptos válidos SIN tarjeta
PATRON_CONCEPTO_SIN_TARJETA = re.compile(
    r'^(\d{2}/\d{2}/\d{4})\s+'    # Fecha
    r'(.+?)\s+'                      # Detalle
    r'([\d]{1,3}(?:\.[\d]{3})*,[\d]{2}-?)\s*$'  # Importe uy
)


class SantanderPDFError(Exception):
    """Excepción base para errores de procesamiento de PDF Santander."""
    pass


class PasswordRequiredError(SantanderPDFError):
    """El PDF está encriptado y requiere contraseña."""
    pass


class InvalidPasswordError(SantanderPDFError):
    """La contraseña proporcionada es incorrecta."""
    pass


class InvalidPDFError(SantanderPDFError):
    """El archivo no es un PDF válido o está corrupto."""
    pass


# ============================================================================
# FUNCIONES DE VALIDACIÓN Y FILTRADO
# ============================================================================

def es_linea_ruido(linea: str) -> bool:
    """
    Determina si una línea es ruido (metadata/resumen) y debe descartarse.
    
    Returns:
        True si la línea debe descartarse, False si puede ser transacción.
    """
    linea_upper = linea.upper()
    
    # 1. Blacklist de palabras clave
    for palabra in BLACKLIST_PALABRAS:
        if palabra in linea_upper:
            return True
    
    # 2. Línea sin letras (solo números, puntuación, espacios)
    if not re.search(r'[A-Za-z]', linea):
        return True
    
    # 3. Fecha corrupta/pegada a otros números (header del PDF)
    if PATRON_FECHA_CORRUPTA.match(linea):
        return True
    
    # 4. Línea muy corta (< 15 chars) probablemente no es transacción
    if len(linea.strip()) < 15:
        return True
    
    return False


def parse_importe(monto_str: str) -> float:
    """
    Convierte un monto en formato uruguayo a float con signo correcto.
    
    Formato uruguayo: 1.234,56 (punto = miles, coma = decimales)
    Negativo: trailing "-" (ej: 741,96-)
    
    Args:
        monto_str: String con el monto (ej: "1.234,56-")
    
    Returns:
        Float con signo correcto (ej: -1234.56)
    """
    monto_str = monto_str.strip()
    
    # Detectar negativo (trailing -)
    negativo = monto_str.endswith('-')
    if negativo:
        monto_str = monto_str[:-1]
    
    # Convertir formato: quitar puntos de miles, cambiar coma por punto
    monto_str = monto_str.replace(".", "").replace(",", ".")
    
    try:
        valor = float(monto_str)
        return -valor if negativo else valor
    except ValueError:
        return 0.0


def validar_detalle(detalle: str) -> bool:
    """
    Valida que el detalle sea legítimo (contenga al menos 1 letra).
    
    Args:
        detalle: String con el detalle de la transacción
    
    Returns:
        True si es válido, False si parece ruido
    """
    # Debe tener al menos 1 letra
    if not re.search(r'[A-Za-z]', detalle):
        return False
    
    # No debe ser solo espacios
    if not detalle.strip():
        return False
    
    return True


def desencriptar_pdf(file_bytes: bytes, password: str = None) -> PdfReader:
    """Abre un PDF desde bytes y lo desencripta si es necesario."""
    try:
        pdf_stream = BytesIO(file_bytes)
        reader = PdfReader(pdf_stream)
    except Exception as e:
        raise InvalidPDFError(f"Archivo inválido: no se pudo leer como PDF. Error: {str(e)}")
    
    if reader.is_encrypted:
        if not password:
            raise PasswordRequiredError("El PDF está encriptado.")
        
        try:
            decrypt_result = reader.decrypt(password)
            if decrypt_result == 0:
                raise InvalidPasswordError("Contraseña incorrecta.")
        except InvalidPasswordError:
            raise
        except Exception as e:
            raise InvalidPasswordError(f"Contraseña incorrecta. Error: {str(e)}")
    
    return reader


def check_pdf_encrypted(file_bytes: bytes) -> bool:
    """Verifica si un PDF está encriptado sin intentar desencriptarlo."""
    try:
        pdf_stream = BytesIO(file_bytes)
        reader = PdfReader(pdf_stream)
        return reader.is_encrypted
    except Exception:
        return True


def extraer_texto_completo(reader: PdfReader) -> str:
    """Extrae todo el texto del PDF."""
    texto = ""
    for page in reader.pages:
        texto += page.extract_text() or ""
    return texto


def _es_devolucion_ley(detalle: str) -> bool:
    """Helper interno: verifica si es devolución de Ley Inclusión Financiera."""
    detalle_upper = detalle.upper()
    return 'LEY INCL FINANC' in detalle_upper or 'LEY INCL' in detalle_upper


def _es_total_dev_ley(detalle: str) -> bool:
    """Helper interno: verifica si es línea TOTAL DEV LEY (corte)."""
    return 'TOTAL DEV LEY' in detalle.upper()


def extraer_movimientos(texto: str) -> tuple:
    """
    Extrae movimientos del texto del PDF de Santander.
    
    REGLAS (v2 - fail-safe):
    - Solo captura líneas que cumplan el PATRON_TRANSACCION_FUERTE
    - Descarta cualquier línea que contenga palabras de BLACKLIST
    - Descarta líneas sin letras en el detalle
    - Descarta líneas con fecha corrupta (pegada a números)
    - CORTA el parseo cuando encuentra marcadores de fin
    
    Returns:
        Tuple (DataFrame, dict_validacion)
    """
    movimientos = []
    total_dev_ley_pdf = None
    
    lineas = texto.split('\n')
    en_movimientos = False
    
    # Marcadores de inicio/fin de sección de movimientos
    MARCADORES_FIN = ['TOTAL DEV LEY', 'SALDO CONTADO', 'IMPORTE TOTAL', 'P.MINIMO', 'P.CONTADO']
    
    for linea in lineas:
        linea_original = linea
        linea = linea.strip()
        
        # Skip líneas vacías
        if not linea:
            continue
        
        # Detectar inicio de sección de movimientos
        if 'SALDO ANTERIOR' in linea.upper():
            en_movimientos = True
            continue  # No procesar esta línea como movimiento
        
        # Detectar fin de sección (CORTE)
        linea_upper = linea.upper()
        es_fin = False
        for marcador in MARCADORES_FIN:
            if marcador in linea_upper:
                # Guardar TOTAL DEV LEY si existe
                if 'TOTAL DEV LEY' in linea_upper:
                    match_total = re.search(r'([\d.,]+(?:-)?)\s*$', linea)
                    if match_total:
                        total_dev_ley_pdf = abs(parse_importe(match_total.group(1)))
                es_fin = True
                break
        
        if es_fin:
            break
        
        if not en_movimientos:
            continue
        
        # FILTRO 1: Es línea de ruido?
        if es_linea_ruido(linea):
            continue
        
        # FILTRO 2: Aplicar patrón FUERTE
        match = PATRON_TRANSACCION_FUERTE.match(linea)
        if not match:
            # Si no cumple el patrón fuerte, evaluar si es concepto válido SIN tarjeta
            linea_up = linea_upper
            if any(conc in linea_up for conc in CONCEPTOS_VALIDOS):
                match_conc = PATRON_CONCEPTO_SIN_TARJETA.match(linea)
                if match_conc:
                    fecha_c, detalle_c, monto_c = match_conc.groups()
                    detalle_c = detalle_c.strip()
                    if validar_detalle(detalle_c):
                        movimientos.append({
                            'Fecha': fecha_c,
                            'Tarjeta': '',
                            'Detalle': detalle_c,
                            'Importe $': parse_importe(monto_c),
                            'Importe U$S': 0.0
                        })
                        continue
            # No cumple patrón ni conceptos -> descartar
            continue
        
        fecha, tarjeta, detalle, monto_str = match.groups()
        detalle = detalle.strip()
        
        # FILTRO 3: Validar que el detalle tenga letras
        if not validar_detalle(detalle):
            continue
        
        # FILTRO 4: Validar que tarjeta sea exactamente 3 dígitos
        if not re.fullmatch(r'\d{3}', tarjeta):
            continue
        
        # Transacción válida - agregar
        movimientos.append({
            'Fecha': fecha,
            'Tarjeta': tarjeta,
            'Detalle': detalle,
            'Importe $': parse_importe(monto_str),
            'Importe U$S': 0.0
        })
    
    # Crear DataFrame
    df = pd.DataFrame(movimientos)
    
    if df.empty:
        df = pd.DataFrame(columns=['Fecha', 'Tarjeta', 'Detalle', 'Importe $', 'Importe U$S'])
    
    validacion = _calcular_validacion_devoluciones(df, total_dev_ley_pdf)
    
    return df, validacion


def _calcular_validacion_devoluciones(df: pd.DataFrame, total_dev_ley_pdf: float) -> dict:
    """Valida suma de devoluciones vs TOTAL DEV LEY."""
    validacion = {
        'total_dev_ley_pdf': total_dev_ley_pdf,
        'suma_devoluciones': 0.0,
        'diferencia': 0.0,
        'warning': None
    }
    
    if df.empty:
        return validacion
    
    mask_dev = df['Detalle'].apply(_es_devolucion_ley)
    suma_dev = abs(df.loc[mask_dev, 'Importe $'].sum())
    validacion['suma_devoluciones'] = suma_dev
    
    if total_dev_ley_pdf is not None:
        diferencia = abs(total_dev_ley_pdf - suma_dev)
        validacion['diferencia'] = diferencia
        
        if diferencia > 0.50:
            validacion['warning'] = (
                f"Validacion devoluciones: suma ({suma_dev:.2f}) vs "
                f"TOTAL DEV LEY ({total_dev_ley_pdf:.2f}), dif={diferencia:.2f}"
            )
    
    return validacion


def extraer_resumen(texto: str) -> dict:
    """Extrae campos de resumen del texto del PDF."""
    resumen = {
        'saldo_anterior': 0.0,
        'saldo_contado': 0.0,
        'pago_minimo': 0.0,
        'pago_contado': 0.0
    }
    
    match = re.search(r'SALDO ANTERIOR\s+([\d.,]+)', texto)
    if match:
        resumen['saldo_anterior'] = parse_importe(match.group(1))
    
    match = re.search(r'SALDO CONTADO\s+([\d.,]+)', texto)
    if match:
        resumen['saldo_contado'] = parse_importe(match.group(1))
    
    match = re.search(r'P\.?Minimo:?\s*([\d.,]+)', texto, re.IGNORECASE)
    if match:
        resumen['pago_minimo'] = parse_importe(match.group(1))
    
    match = re.search(r'P\.?Contado:?\s*([\d.,]+)', texto, re.IGNORECASE)
    if match:
        resumen['pago_contado'] = parse_importe(match.group(1))
    
    return resumen


def extraer_movimientos_desde_pdf(file_bytes: bytes, password: str = None) -> tuple:
    """
    Función principal para extraer movimientos de un PDF de Santander.
    
    Returns:
        Tuple (DataFrame, validacion_dict)
    """
    reader = desencriptar_pdf(file_bytes, password)
    texto = extraer_texto_completo(reader)
    return extraer_movimientos(texto)


def procesar_pdf_santander(file_bytes: bytes, password: str = None) -> dict:
    """Procesa un PDF de Santander completo."""
    reader = desencriptar_pdf(file_bytes, password)
    was_encrypted = hasattr(reader, '_encryption') and reader._encryption is not None
    
    texto = extraer_texto_completo(reader)
    df, validacion = extraer_movimientos(texto)
    resumen = extraer_resumen(texto)
    
    return {
        'df': df,
        'resumen': resumen,
        'validacion': validacion,
        'total_pages': len(reader.pages),
        'was_encrypted': was_encrypted
    }


# ============================================================================
# TESTS RÁPIDOS - Validación del patrón fuerte
# ============================================================================

def _test_parser():
    """
    Tests rápidos para validar el parsing de transacciones.
    Ejecutar con: python -c "from bancos.santander.parser import _test_parser; _test_parser()"
    """
    print("=" * 60)
    print("TESTS DEL PARSER SANTANDER (v2 - fail-safe)")
    print("=" * 60)
    
    # Casos de prueba
    casos = [
        # (línea, debe_ser_valida, importe_esperado, descripcion)
        ("07/12/2025 399 PAGOS 741,96-", True, -741.96, "Pago válido (negativo)"),
        ("15/01/2026 579 TIENDA MOSCA 1/3 1.234,56", True, 1234.56, "Compra en cuotas"),
        ("20/01/2026 123 MERCADOLIBRE COMPRA 500,00", True, 500.0, "Compra simple"),
        ("SALDO ANTERIOR 741,96", False, None, "Saldo anterior (blacklist)"),
        ("SALDO CONTADO 15.000,00", False, None, "Saldo contado (blacklist)"),
        ("28/01/2026 770068579200 41.090", False, None, "Header corrupto (fecha pegada)"),
        ("13/02/2026770068579200 41.090", False, None, "Fecha pegada a números"),
        ("P.MINIMO 500,00", False, None, "Pago mínimo (blacklist)"),
        ("LIMITE DE CREDITO 50.000,00", False, None, "Límite (blacklist)"),
        ("770068579200 41.090", False, None, "Solo números sin fecha"),
        ("", False, None, "Línea vacía"),
        ("07/12/2025 39 PAGOS 741,96-", False, None, "Tarjeta 2 dígitos (inválido)"),
        ("07/12/2025 3999 PAGOS 741,96-", False, None, "Tarjeta 4 dígitos (inválido)"),
        # Conceptos válidos SIN tarjeta
        ("08/01/2026 INTERESES FINANCIEROS 320,00", True, 320.0, "Intereses sin tarjeta"),
        ("09/01/2026 MULTA POR MORA LEY 18212 150,00", True, 150.0, "Multa por mora sin tarjeta"),
        ("10/01/2026 I.V.A. 22% $ 70,40", True, 70.40, "IVA 22% sin tarjeta"),
    ]
    
    errores = 0
    
    for linea, debe_ser_valida, importe_esperado, descripcion in casos:
        # Simular el parsing
        es_ruido = es_linea_ruido(linea) if linea else True
        match = PATRON_TRANSACCION_FUERTE.match(linea) if linea and not es_ruido else None
        
        es_valida = False
        importe = None
        
        if match and not es_ruido:
            fecha, tarjeta, detalle, monto_str = match.groups()
            if validar_detalle(detalle) and re.fullmatch(r'\d{3}', tarjeta):
                es_valida = True
                importe = parse_importe(monto_str)
        else:
            # Simular lógica de conceptos válidos sin tarjeta
            linea_up = linea.upper() if linea else ""
            if not es_ruido and any(conc in linea_up for conc in CONCEPTOS_VALIDOS):
                match_conc = PATRON_CONCEPTO_SIN_TARJETA.match(linea)
                if match_conc:
                    f, d, m = match_conc.groups()
                    if validar_detalle(d):
                        es_valida = True
                        importe = parse_importe(m)
        
        # Verificar resultado
        ok = es_valida == debe_ser_valida
        if debe_ser_valida and ok and importe_esperado is not None:
            ok = abs(importe - importe_esperado) < 0.01
        
        status = "✓ PASS" if ok else "✗ FAIL"
        if not ok:
            errores += 1
        
        print(f"{status} | {descripcion}")
        print(f"       Línea: '{linea[:50]}{'...' if len(linea) > 50 else ''}'")
        print(f"       Esperado: válida={debe_ser_valida}, importe={importe_esperado}")
        print(f"       Obtenido: válida={es_valida}, importe={importe}")
        print()
    
    print("=" * 60)
    if errores == 0:
        print(f"TODOS LOS TESTS PASARON ({len(casos)} casos)")
    else:
        print(f"FALLARON {errores} de {len(casos)} tests")
    print("=" * 60)
    
    return errores == 0


if __name__ == "__main__":
    _test_parser()
