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

    nombre_archivo = archivo.filename

    os.makedirs("archivos_temp", exist_ok=True)

    nombre_pdf = f"{uuid.uuid4().hex}.pdf"
    ruta_pdf = os.path.join("archivos_temp", nombre_pdf)
    archivo.save(ruta_pdf)

    df = extraer_movimientos_desde_pdf(ruta_pdf)

    # Asegurar que los importes sean numéricos antes de cualquier suma
    df["Importe $"] = pd.to_numeric(df["Importe $"], errors="coerce")
    df["Importe U$S"] = pd.to_numeric(df["Importe U$S"], errors="coerce")

    # Detectar número de cuota y total de cuotas
    df["cuotas_pagas"], df["cuotas_totales"] = zip(*df["Detalle"].apply(numero_cuotas))

    # Calcular cuotas restantes
    df["cuotas_restantes"] = df["cuotas_totales"] - df["cuotas_pagas"]

    # Validar si es cuota
    df["es_cuota"] = df.apply(
        lambda row: "SI" if es_cuota(row["Detalle"]) and 0 <= row["cuotas_restantes"] <= 11 else "NO",
        axis=1
    )

    # Calcular totales (con columnas numéricas válidas)
    total_cuotas_pesos = df.loc[df["es_cuota"] == "SI", "Importe $"].sum(skipna=True)
    total_cuotas_dolares = df.loc[df["es_cuota"] == "SI", "Importe U$S"].sum(skipna=True)
    total_corrientes_pesos = df.loc[df["es_cuota"] == "NO", "Importe $"].sum(skipna=True)
    total_corrientes_dolares = df.loc[df["es_cuota"] == "NO", "Importe U$S"].sum(skipna=True)
    total_pesos = total_cuotas_pesos + total_corrientes_pesos
    total_dolares = df["Importe U$S"].sum(skipna=True)

    porcentaje_cuotas_pesos = round((total_cuotas_pesos / total_pesos) * 100, 2) if total_pesos > 0 else 0

    # ---- PROYECCIÓN DE CUOTAS POR MES ----
    df_cuotas = df[df["es_cuota"] == "SI"].copy()
    df_cuotas_restantes = df_cuotas.groupby('cuotas_restantes', as_index=False)['Importe $'].sum()

    # Determinar el último mes con datos (dinámico)
    if len(df_cuotas_restantes) > 0:
        ultimo_mes = int(df_cuotas_restantes["cuotas_restantes"].max())
    else:
        ultimo_mes = 0

    # Crear un DataFrame con los meses desde 0 hasta el último mes presente
    meses_completos = pd.DataFrame({'cuotas_restantes': range(ultimo_mes + 1)})

    # Hacer un merge para completar los meses faltantes con 0 en los importes
    df_cuotas_restantes = meses_completos.merge(df_cuotas_restantes, on="cuotas_restantes", how="left").fillna(0)

    # Calcular el saldo acumulativo inverso
    df_cuotas_restantes = df_cuotas_restantes.sort_values(by="cuotas_restantes", ascending=True)
    df_cuotas_restantes["saldo_mes"] = df_cuotas_restantes["Importe $"].iloc[::-1].cumsum().iloc[::-1]

    # ---- CUOTAS DEL MES ACTUAL (primera cuota) ----
    cuotas_mes_actual_df = df[
        (df["es_cuota"] == "SI") & (df["cuotas_pagas"] == 1)
    ]

    cuotas_mes_actual_html = cuotas_mes_actual_df.fillna("").to_html(
        classes='min-w-full', index=True, na_rep=""
    )
    cuotas_mes_total_pesos = cuotas_mes_actual_df["Importe $"].sum(skipna=True)
    cuotas_mes_total_dolares = cuotas_mes_actual_df["Importe U$S"].sum(skipna=True)
    cuotas_mes_cantidad = len(cuotas_mes_actual_df)

    # Preparar tabla HTML sin columnas auxiliares
    df_html = df.drop(columns=["cuotas_pagas", "cuotas_totales", "cuotas_restantes"], errors='ignore').fillna("")

    # Guardar Excel temporal
    nombre_excel = f"{uuid.uuid4().hex}.xlsx"
    ruta_excel = os.path.join("archivos_temp", nombre_excel)
    df.to_excel(ruta_excel, index=False)

    # Eliminar archivo PDF
    os.remove(ruta_pdf)

    cuotas_restantes_list = df_cuotas_restantes['cuotas_restantes'].tolist()
    montos_cuotas_restantes_list = df_cuotas_restantes['saldo_mes'].tolist()

    # Evitar errores de índice en plantilla cuando no hay cuotas o solo un mes
    if not cuotas_restantes_list:
        cuotas_restantes_list = [0]
    if len(montos_cuotas_restantes_list) == 0:
        montos_cuotas_restantes_list = [0, 0]
    elif len(montos_cuotas_restantes_list) == 1:
        montos_cuotas_restantes_list.append(montos_cuotas_restantes_list[0])

    contexto = {
        "tabla": df_html.to_html(classes='min-w-full', index=False, na_rep=""),
        "total_pesos": round(total_pesos, 2),
        "total_dolares": round(total_dolares, 2),
        "total_cuotas_pesos": round(total_cuotas_pesos, 2),
        "total_cuotas_dolares": round(total_cuotas_dolares, 2),
        "total_corrientes_pesos": round(total_corrientes_pesos, 2),
        "total_corrientes_dolares": round(total_corrientes_dolares, 2),
        "porcentaje_cuotas_pesos": porcentaje_cuotas_pesos,
        "cuotas_restantes": cuotas_restantes_list,
        "montos_cuotas_restantes": montos_cuotas_restantes_list,
        "nombre_archivo": nombre_archivo,
        "nombre_excel": nombre_excel,
        "cuotas_mes_actual": cuotas_mes_actual_html,
        "cuotas_mes_total_pesos": round(cuotas_mes_total_pesos, 2),
        "cuotas_mes_total_dolares": round(cuotas_mes_total_dolares, 2),
        "cuotas_mes_cantidad": cuotas_mes_cantidad,
        "nombre_banco": "Itaú",
        "banco_color": "orange",
    }

    return render_template("resultado.html", **contexto)
