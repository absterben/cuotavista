from flask import Blueprint, request, render_template
from .utils import calculo_totales, es_cuota, numero_cuotas
from .parser import depurar_archivo

import pandas as pd
import uuid
import os

brou_bp = Blueprint("brou", __name__)


@brou_bp.route("/resultado", methods=["POST"])
def pagina_resultado():
    try:
        if "file" not in request.files:
            return "No se envió ningún archivo"
        
        file = request.files["file"]
        if file.filename == "":
            return "Nombre de archivo vacío"

        nombre_archivo = file.filename
        
        # Depura el archivo cargado
        result = depurar_archivo(file)
        # El parser puede retornar df o (None, error_msg)
        if isinstance(result, tuple):
            df, error_msg = result
            if df is None:
                raise ValueError(f"El archivo no se pudo procesar: {error_msg}")
        else:
            df = result
        if df is None:
            raise ValueError("El archivo no se pudo procesar correctamente.")

        # Calcular cuotas: número actual, total y restantes
        df[['cuotas_pagas', 'cuotas_totales']] = df['Descripción'].apply(lambda x: pd.Series(numero_cuotas(x)))
        df['cuotas_restantes'] = df['cuotas_totales'] - df['cuotas_pagas']

        # Marcar como cuota si cumple el patrón y tiene entre 0-11 cuotas restantes
        df["es_cuota"] = df.apply(
            lambda row: "SI" if es_cuota(row["Descripción"]) and 0 <= row["cuotas_restantes"] <= 11 else "NO",
            axis=1
        )

        # Calcular totales generales y por cuotas
        total_pesos, total_dolares = calculo_totales(df)
        total_cuotas_pesos, total_cuotas_dolares = calculo_totales(df, mask=df["es_cuota"] == "SI")

        # Generar proyección de liberación de cuotas por mes
        df_cuotas_restantes = df.groupby('cuotas_restantes', as_index=False)['Importe $'].sum()

        # ---- COMPLETAR HASTA EL ÚLTIMO MES PRESENTE ----
        # Determinar el último mes con datos (dinámico) y asegurarse de que sea entero
        ultimo_mes = int(df_cuotas_restantes["cuotas_restantes"].max())

        # Crear un DataFrame con los meses desde 0 hasta el último mes presente
        meses_completos = pd.DataFrame({'cuotas_restantes': range(ultimo_mes + 1)})

        # Hacer un merge para completar los meses faltantes con 0 en los importes
        df_cuotas_restantes = meses_completos.merge(df_cuotas_restantes, on="cuotas_restantes", how="left").fillna(0)

        # ---- CALCULAR EL SALDO CORRECTAMENTE ----
        # Hacer una resta acumulativa inversa
        df_cuotas_restantes = df_cuotas_restantes.sort_values(by="cuotas_restantes", ascending=True)  # Asegurar orden
        df_cuotas_restantes["saldo_mes"] = df_cuotas_restantes["Importe $"].iloc[::-1].cumsum().iloc[::-1]

        # Exportar proyección a HTML
        df_cuotas_restantes_html = df_cuotas_restantes.to_html(index=False, na_rep="")

        df.index.name = None
        df.reset_index(drop=True, inplace=True)

        # Crear tabla con los datos crudos
        data_html = df.drop(columns=["cuotas_pagas","cuotas_totales","cuotas_restantes"]).to_html(na_rep="", classes="table w-full table-auto border border-gray-300 text-sm")
        
        # Preparar archivo Excel para descarga
        os.makedirs("archivos_temp", exist_ok=True)
        nombre_excel = f"{uuid.uuid4().hex}.xlsx"
        ruta_excel = os.path.join("archivos_temp", nombre_excel)

        # Filtrar cuotas nuevas del mes actual (primera cuota)
        cuotas_mes_actual_df = df[
            (df["es_cuota"] == "SI") & (df["cuotas_pagas"] == 1)
        ]

        cuotas_mes_actual_html = cuotas_mes_actual_df.fillna("").to_html(
            classes='min-w-full', index=True, na_rep=""
        )
        cuotas_mes_total_pesos = cuotas_mes_actual_df["Importe $"].sum(skipna=True)
        cuotas_mes_total_dolares = cuotas_mes_actual_df["Importe U$S"].sum(skipna=True)
        cuotas_mes_cantidad = len(cuotas_mes_actual_df)

        # Guardar Excel
        df.to_excel(ruta_excel, index=True)
        
        cuotas_restantes_list = df_cuotas_restantes['cuotas_restantes'].tolist()
        montos_cuotas_restantes_list = df_cuotas_restantes['saldo_mes'].tolist()

        # Evitar errores de índice en plantilla cuando no hay cuotas o solo un mes
        if not cuotas_restantes_list:
            cuotas_restantes_list = [0]
        if len(montos_cuotas_restantes_list) == 0:
            montos_cuotas_restantes_list = [0, 0]
        elif len(montos_cuotas_restantes_list) == 1:
            montos_cuotas_restantes_list.append(montos_cuotas_restantes_list[0])

        # Guardia: evitar zero division en porcentaje
        if total_pesos > 0:
            porcentaje_cuotas_pesos = round(total_cuotas_pesos / total_pesos * 100, 2)
        else:
            porcentaje_cuotas_pesos = 0
        
        contexto = {
            "tabla": data_html,
            "total_pesos": total_pesos,
            "total_dolares": total_dolares,
            "total_cuotas_pesos": total_cuotas_pesos,
            "total_cuotas_dolares": total_cuotas_dolares,
            "total_corrientes_pesos": total_pesos - total_cuotas_pesos,
            "total_corrientes_dolares": total_dolares - total_cuotas_dolares,
            "porcentaje_cuotas_pesos": porcentaje_cuotas_pesos,
            "df_cuotas_restantes": df_cuotas_restantes_html,
            "cuotas_restantes": cuotas_restantes_list,
            "montos_cuotas_restantes": montos_cuotas_restantes_list,
            "nombre_archivo": nombre_archivo,
            "nombre_excel": nombre_excel,
            "cuotas_mes_actual": cuotas_mes_actual_html,
            "cuotas_mes_total_pesos": round(cuotas_mes_total_pesos, 2),
            "cuotas_mes_total_dolares": round(cuotas_mes_total_dolares, 2),
            "cuotas_mes_cantidad": cuotas_mes_cantidad,
            "nombre_banco": "BROU",
            "banco_color": "blue",
        }

        # Mínimo cambio: asegurar saldo_anterior en el contexto (default 0)
        contexto.setdefault("saldo_anterior", 0)
        contexto.setdefault("total_pesos_con_saldo_anterior", contexto["total_pesos"] + contexto["saldo_anterior"])

        return render_template("resultado.html", **contexto)
    except ValueError as e:
        return render_template("error.html", mensaje=str(e)), 400  # Error del cliente
    except Exception as e:
        return render_template("error.html", mensaje="Error inesperado: " + str(e)), 500  # Error del servidor