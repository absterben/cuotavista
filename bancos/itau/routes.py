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

    df["es_cuota"] = df["Detalle"].apply(es_cuota)
    df["Nro cuota"], df["Total cuotas"] = zip(*df["Detalle"].apply(numero_cuotas))


    nombre_excel = f"{uuid.uuid4().hex}.xlsx"
    ruta_excel = os.path.join("archivos_temp", nombre_excel)
    df.to_excel(ruta_excel, index=False)

    os.remove(ruta_pdf)

    return render_template("resultado_itau.html",
        #nombre_archivo=nombre_excel,
        nombre_excel=nombre_excel,
        tabla=df.to_html(classes='min-w-full', index=False, na_rep=""),
        total_pesos=round(df["Importe $"].sum(skipna=True), 2),
        total_dolares=round(df["Importe U$S"].sum(skipna=True), 2),
        total_corrientes_pesos = round(1,2),
        total_cuotas_pesos = round(2,2),
    )

