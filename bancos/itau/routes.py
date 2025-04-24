# bancos/itau/routes.py

from flask import Blueprint, request, render_template, send_file
from bancos.itau.parser import extraer_movimientos_desde_pdf
from bancos.itau.utils import es_cuota, numero_cuotas
import pandas as pd
import os
import uuid

itau_bp = Blueprint("itau", __name__)

@itau_bp.route("/resultado", methods=["POST"])
def procesar_pdf_itau():
    archivo = request.files.get("archivo")
    if not archivo:
        return "No se subió ningún archivo", 400

    os.makedirs("archivos_temp", exist_ok=True)

    nombre_pdf = f"{uuid.uuid4().hex}.pdf"
    ruta_pdf = os.path.join("archivos_temp", nombre_pdf)
    archivo.save(ruta_pdf)

    df = extraer_movimientos_desde_pdf(ruta_pdf)

    # Asegurar que los importes sean numéricos antes de cualquier suma
    df["Importe $"] = pd.to_numeric(df["Importe $"], errors="coerce")
    df["Importe U$S"] = pd.to_numeric(df["Importe U$S"], errors="coerce")

    # Detectar número de cuota y total de cuotas
    df["Nro cuota"], df["Total cuotas"] = zip(*df["Detalle"].apply(numero_cuotas))

    # Calcular cuotas restantes
    df["cuotas_restantes"] = df["Total cuotas"] - df["Nro cuota"]

    # Validar si es cuota
    df["es_cuota"] = df.apply(
        lambda row: "SI" if es_cuota(row["Detalle"]) and 0 <= row["cuotas_restantes"] <= 11 else "NO",
        axis=1
    )

    # Calcular totales (con columnas numéricas válidas)
    total_cuotas_pesos = df.loc[df["es_cuota"] == "SI", "Importe $"].sum(skipna=True)
    total_corrientes_pesos = df.loc[df["es_cuota"] == "NO", "Importe $"].sum(skipna=True)
    total_pesos = total_cuotas_pesos + total_corrientes_pesos
    total_dolares = df["Importe U$S"].sum(skipna=True)

    porcentaje_cuotas_pesos = round((total_cuotas_pesos / total_pesos) * 100, 2) if total_pesos > 0 else 0
    porcentaje_corrientes_pesos = round((total_corrientes_pesos / total_pesos) * 100, 2) if total_pesos > 0 else 0

    # Reemplazar valores nulos SOLO para mostrar en HTML
    df_html = df.fillna("")

    # Guardar Excel temporal (opcional)
    nombre_excel = f"{uuid.uuid4().hex}.xlsx"
    ruta_excel = os.path.join("archivos_temp", nombre_excel)
    df.to_excel(ruta_excel, index=False)

    # Eliminar archivo PDF
    os.remove(ruta_pdf)

    return render_template("resultado_itau.html",
        nombre_excel=nombre_excel,
        tabla=df_html.to_html(classes='min-w-full', index=False, na_rep=""),
        total_pesos=round(total_pesos, 2),
        total_dolares=round(total_dolares, 2),
        total_corrientes_pesos=round(total_corrientes_pesos, 2),
        total_cuotas_pesos=round(total_cuotas_pesos, 2),
        porcentaje_cuotas_pesos=porcentaje_cuotas_pesos,
        porcentaje_corrientes_pesos=porcentaje_corrientes_pesos,
    )
