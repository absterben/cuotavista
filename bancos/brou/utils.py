import pandas as pd
import re
import os

def calculo_totales(df, mask=None):
    """Calcula totales generales o con filtro opcional"""
    
    if mask is not None:
        df = df.loc[mask]  # Aplica la máscara si se proporciona

    total_pesos = round(df["Importe $"].sum(), 2)
    total_dolares = round(df["Importe U$S"].sum(), 2)

    return total_pesos, total_dolares


def es_cuota(descripcion):
    descripcion = descripcion.strip()  # Elimina espacios antes y después
    
    if "/" in descripcion:
        partes = descripcion.split("/")  # Divide el texto en dos partes
        
        if len(partes) >= 2:
            num1_str = partes[-2].strip()  # Penúltimo elemento
            num2_str = partes[-1].strip()  # Último elemento

            # Tomar los últimos dos dígitos de num1_str
            num1 = "".join(filter(str.isdigit, num1_str))[-2:]  # Extrae solo números y toma los últimos 2

            # Tomar los primeros dos dígitos de num2_str
            num2 = "".join(filter(str.isdigit, num2_str))[:2]  # Extrae solo números y toma los primeros 2

            if num1.isdigit() and num2.isdigit():  # Verifica que sean números antes de convertirlos
                num1, num2 = int(num1), int(num2)  # Convierte a entero
                return "SI"

    return "NO"


def numero_cuotas(descripcion):
    descripcion = descripcion.strip()
    
    if "/" in descripcion:
        partes = descripcion.split("/")
        if len(partes) >= 2:
            num1_str = partes[-2].strip()  # Penúltima parte antes del "/"
            num2_str = partes[-1].strip()  # Última parte después del "/"

            # Extraer el último número de num1_str (evitando que tome valores previos)
            num1 = "".join(filter(str.isdigit, num1_str.split()[-1])) if " " in num1_str else "".join(filter(str.isdigit, num1_str))[-2:]

            # Extraer los primeros 2 dígitos de num2_str
            num2 = "".join(filter(str.isdigit, num2_str))[:2]

            if num1.isdigit() and num2.isdigit():  # Asegurar que sean números válidos
                return int(num1), int(num2)

    return None, None


categorization_dict = {
    "ancap": "COMBUSTIBLES",
    "ley 18.083": "COMBUSTIBLES",
    "uber": "TRANSPORTE",
    "ta ta": "SUPERMERCADO",
    "tata": "SUPERMERCADO",
    "almacen": "SUPERMERCADO",
    "brou": "FINANZAS",
    "apple": "ENTRETENIMIENTO",
    "deudor": "FINANZAS",
    "google": "ENTRETENIMIENTO",
    "youtube": "ENTRETENIMIENTO",
    "ley 17.934": "FINANZAS",
    "turil": "TRANSPORTE",
    "movistar": "HOGAR",
    "antel": "HOGAR",
    "buquebus": "TRANSPORTE",
    "mercadopago": "COMPRAS WEB",
    "mcdonalds": "RESTAURANTES",
    "mostaza": "RESTAURANTES",
    "cot": "TRANSPORTE",
    "super": "SUPERMERCADO"
    }  

# Función para categorizar usando el diccionario
def categorize_transaction(datos):
    for keyword, category in categorization_dict.items():
        if keyword in datos.lower():
            return category
    return "OTROS"  # Si no encuentra una categoría, marca como "OTROS"
