# bancos/scotiabank/routes.py

from flask import Blueprint, request, render_template
from bancos.scotiabank.parser import extraer_movimientos_desde_pdf
from bancos.scotiabank.utils import es_cuota, numero_cuotas
import pandas as pd
import os
import uuid

scotia_bp = Blueprint("scotiabank", __name__)

@scotia_bp.route("/resultado", methods=["POST"])
def procesar_pdf_scotia():
    archivo = request.files.get("archivo")
    if not archivo:
        return "No se subió ningún archivo", 400

    os.makedirs("archivos_temp", exist_ok=True)
    nombre_pdf = f"{uuid.uuid4().hex}.pdf"
    ruta_pdf = os.path.join("archivos_temp", nombre_pdf)
    archivo.save(ruta_pdf)

    df = extraer_movimientos_desde_pdf(ruta_pdf)
    df["Importe $"] = pd.to_numeric(df["Importe $"], errors="coerce")
    df["Importe U$S"] = pd.to_numeric(df["Importe U$S"], errors="coerce")

    df["Nro cuota"], df["Total cuotas"] = zip(*df["Detalle"].apply(numero_cuotas))
    df["cuotas_restantes"] = df["Total cuotas"] - df["Nro cuota"]

    df["es_cuota"] = df.apply(
        lambda row: "SI" if es_cuota(row["Detalle"]) and 0 <= row["cuotas_restantes"] <= 11 else "NO",
        axis=1
    )

    total_cuotas_pesos = df.loc[df["es_cuota"] == "SI", "Importe $"].sum(skipna=True)
    total_corrientes_pesos = df.loc[df["es_cuota"] == "NO", "Importe $"].sum(skipna=True)
    total_pesos = total_cuotas_pesos + total_corrientes_pesos
    total_dolares = df["Importe U$S"].sum(skipna=True)

    porcentaje_cuotas_pesos = round((total_cuotas_pesos / total_pesos) * 100, 2) if total_pesos > 0 else 0
    porcentaje_corrientes_pesos = round((total_corrientes_pesos / total_pesos) * 100, 2) if total_pesos > 0 else 0

    df_html = df.fillna("")

    nombre_excel = f"{uuid.uuid4().hex}.xlsx"
    ruta_excel = os.path.join("archivos_temp", nombre_excel)
    df.to_excel(ruta_excel, index=False)

    os.remove(ruta_pdf)

    return render_template("resultado_scotiabank.html",
        nombre_excel=nombre_excel,
        tabla=df_html.to_html(classes='min-w-full', index=False, na_rep=""),
        total_pesos=round(total_pesos, 2),
        total_dolares=round(total_dolares, 2),
        total_corrientes_pesos=round(total_corrientes_pesos, 2),
        total_cuotas_pesos=round(total_cuotas_pesos, 2),
        porcentaje_cuotas_pesos=porcentaje_cuotas_pesos,
        porcentaje_corrientes_pesos=porcentaje_corrientes_pesos,
    )
