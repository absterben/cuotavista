#!/usr/bin/env python
import pandas as pd
from bancos.brou.parser import depurar_archivo
from bancos.brou.utils import es_cuota, numero_cuotas

class FakeFile:
    def __init__(self, path):
        self.filename = path
        self.file = open(path, 'rb')

result = depurar_archivo(FakeFile('static/ejemplo_estado_cuenta.xls'))
if isinstance(result, tuple):
    df, error = result
    print(f'Parser error: {error}')
    exit(1)
else:
    df = result

# Replicar la lógica de routes.py de BROU
df[['cuotas_pagas', 'cuotas_totales']] = df['Descripción'].apply(lambda x: pd.Series(numero_cuotas(x)))
df['cuotas_restantes'] = df['cuotas_totales'] - df['cuotas_pagas']

df["es_cuota"] = df.apply(
    lambda row: "SI" if es_cuota(row["Descripción"]) and 0 <= row["cuotas_restantes"] <= 11 else "NO",
    axis=1
)

total_pesos, total_dolares = df["Importe $"].sum(), df["Importe U$S"].sum()
total_cuotas_pesos, total_cuotas_dolares = df[df["es_cuota"] == "SI"][["Importe $", "Importe U$S"]].sum()

# Try the division that might fail
try:
    porcentaje = round(total_cuotas_pesos / total_pesos * 100, 2)
    print(f'total_pesos={total_pesos}, total_cuotas_pesos={total_cuotas_pesos}, porcentaje={porcentaje}')
except ZeroDivisionError as e:
    print(f'Division by zero: {e}')
    porcentaje = 0

print(f'All sums OK')
