# bancos/scotiabank/utils.py

import re

def es_cuota(descripcion):
    descripcion = descripcion.strip()
    if "/" in descripcion:
        partes = descripcion.split("/")
        if len(partes) >= 2:
            num1_str = partes[-2].strip()
            num2_str = partes[-1].strip()
            num1 = "".join(filter(str.isdigit, num1_str))[-2:]
            num2 = "".join(filter(str.isdigit, num2_str))[:2]
            if num1.isdigit() and num2.isdigit():
                return "SI"
    return "NO"

def numero_cuotas(descripcion):
    descripcion = descripcion.strip()
    if "/" in descripcion:
        partes = descripcion.split("/")
        if len(partes) >= 2:
            num1_str = partes[-2].strip()
            num2_str = partes[-1].strip()
            num1 = "".join(filter(str.isdigit, num1_str.split()[-1])) if " " in num1_str else "".join(filter(str.isdigit, num1_str))[-2:]
            num2 = "".join(filter(str.isdigit, num2_str))[:2]
            if num1.isdigit() and num2.isdigit():
                return int(num1), int(num2)
    return None, None
