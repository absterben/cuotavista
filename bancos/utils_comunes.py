"""
Funciones comunes para el análisis de cuotas de tarjetas de crédito.
Usadas por los módulos BROU e Itaú.
"""


def es_cuota(descripcion):
    """
    Determina si una transacción es una cuota basándose en el patrón X/Y.
    Ejemplo: "COMPRA TIENDA 3/12" -> "SI"
    
    Args:
        descripcion: Texto de la descripción del movimiento
        
    Returns:
        "SI" si es cuota, "NO" si no lo es
    """
    descripcion = descripcion.strip()
    
    if "/" in descripcion:
        partes = descripcion.split("/")
        
        if len(partes) >= 2:
            num1_str = partes[-2].strip()
            num2_str = partes[-1].strip()

            # Tomar los últimos dos dígitos de num1_str
            num1 = "".join(filter(str.isdigit, num1_str))[-2:]

            # Tomar los primeros dos dígitos de num2_str
            num2 = "".join(filter(str.isdigit, num2_str))[:2]

            if num1.isdigit() and num2.isdigit():
                return "SI"

    return "NO"


def numero_cuotas(descripcion):
    """
    Extrae el número de cuota actual y el total de cuotas de una descripción.
    Ejemplo: "COMPRA TIENDA 3/12" -> (3, 12)
    
    Args:
        descripcion: Texto de la descripción del movimiento
        
    Returns:
        Tupla (cuota_actual, total_cuotas) o (None, None) si no aplica
    """
    descripcion = descripcion.strip()
    
    if "/" in descripcion:
        partes = descripcion.split("/")
        if len(partes) >= 2:
            num1_str = partes[-2].strip()
            num2_str = partes[-1].strip()

            # Extraer el último número de num1_str
            if " " in num1_str:
                num1 = "".join(filter(str.isdigit, num1_str.split()[-1]))
            else:
                num1 = "".join(filter(str.isdigit, num1_str))[-2:]

            # Extraer los primeros 2 dígitos de num2_str
            num2 = "".join(filter(str.isdigit, num2_str))[:2]

            if num1.isdigit() and num2.isdigit():
                return int(num1), int(num2)

    return None, None


def calculo_totales(df, mask=None):
    """
    Calcula totales de importes en pesos y dólares.
    
    Args:
        df: DataFrame con columnas "Importe $" e "Importe U$S"
        mask: Máscara booleana opcional para filtrar filas
        
    Returns:
        Tupla (total_pesos, total_dolares)
    """
    if mask is not None:
        df = df.loc[mask]

    total_pesos = round(df["Importe $"].sum(), 2)
    total_dolares = round(df["Importe U$S"].sum(), 2)

    return total_pesos, total_dolares
