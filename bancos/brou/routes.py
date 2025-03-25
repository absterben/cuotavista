from flask import Blueprint, request, render_template
from .utils import (
    calculo_totales, es_cuota, numero_cuotas, categorize_transaction
)
from .parser import depurar_archivo

import pandas as pd

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
        df = depurar_archivo(file)

        if df is None:
            raise ValueError("El archivo no se pudo procesar correctamente.")

        # Discierne cuotas de gastos corrientes
        df["es_cuota"] = df["Descripción"].astype(str).apply(es_cuota)


        # Calcular totales en pesos y dolares
        total_pesos, total_dolares = calculo_totales(df)
        # Calcula totales en pesos para cuotas en pesos y dolares
        total_cuotas_pesos, total_cuotas_dolares = calculo_totales(df, mask=df["es_cuota"] == "SI")


        ########################################################## PROCESO DE CATEGORIZACIÓN
        df["categoria"] = df["Descripción"].apply(categorize_transaction)

        df_summary = df.groupby("categoria").agg(
        Cantidad_Transacciones=("Descripción", "count"),
        Total_Importe_Pesos=("Importe $", "sum"),
        Total_Importe_Dolares=("Importe U$S", "sum")
        ).reset_index()

        total_transacciones = df_summary["Cantidad_Transacciones"].sum()
        total_importe_pesos = df_summary["Total_Importe_Pesos"].sum()
        total_importe_dolares = df_summary["Total_Importe_Dolares"].sum()

        df_summary["Porcentaje Transacciones (%)"] = (df_summary["Cantidad_Transacciones"] / total_transacciones) * 100
        df_summary["Porcentaje Importe Pesos (%)"] = (df_summary["Total_Importe_Pesos"] / total_importe_pesos) * 100
        df_summary["Porcentaje Importe Dólares (%)"] = (df_summary["Total_Importe_Dolares"] / total_importe_dolares) * 100

        df_resumido = df_summary.to_html(index=False, na_rep="")
        #######################################################################################

        # Calculo de cuotas totales, pagas y restantes.
        # Aplicamos la función y expandimos a columnas
        df[['cuotas_pagas', 'cuotas_totales']] = df['Descripción'].apply(lambda x: pd.Series(numero_cuotas(x)))

        df['cuotas_restantes'] = df['cuotas_totales'] - df['cuotas_pagas']
        '''
        # Calculamos cuotas restantes
        df_cuotas_restantes = df.groupby('cuotas_restantes')['Importe $'].sum().reset_index()

        df_cuotas_restantes = df.groupby('cuotas_restantes')['Importe $'].sum().reset_index()
        df_cuotas_restantes = df_cuotas_restantes.sort_values(by='cuotas_restantes')



        # Ordenar el DataFrame por 'cuotas_restantes' en orden descendente
        df_cuotas_restantes = df_cuotas_restantes.sort_values(by="cuotas_restantes", ascending=False)

        # Crear la nueva columna 'saldo_mes' sumando acumulativamente desde abajo hacia arriba
        df_cuotas_restantes["saldo_mes"] = df_cuotas_restantes["Importe $"].cumsum()

        # Volver a ordenar el DataFrame de menor a mayor en 'cuotas_restantes'
        df_cuotas_restantes = df_cuotas_restantes.sort_values(by="cuotas_restantes", ascending=True)
        '''

                # Calculo de cuotas totales, pagas y restantes.
        df[['cuotas_pagas', 'cuotas_totales']] = df['Descripción'].apply(lambda x: pd.Series(numero_cuotas(x)))
        df['cuotas_restantes'] = df['cuotas_totales'] - df['cuotas_pagas']

        # Agrupamos y sumamos importes según las cuotas restantes
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

        # ---- EXPORTAR A HTML ----
        df_cuotas_restantes_html = df_cuotas_restantes.to_html(index=False, na_rep="")


        # Crear tabla con cuotas restantes
        df_cuotas_restantes_html = df_cuotas_restantes.to_html(index=False, na_rep="")

        df.index.name = None
        df.reset_index(drop=True, inplace=True)

        # Crear tabla con los datos crudos.
        data_html = df.drop(columns=["categoria","cuotas_pagas","cuotas_totales","cuotas_restantes"]).to_html(na_rep="", classes="table w-full table-auto border border-gray-300 text-sm")
        
        contexto = {
            "tabla": data_html,
            "total_pesos": total_pesos,
            "total_dolares": total_dolares,
            "total_cuotas_pesos": total_cuotas_pesos,
            "total_cuotas_dolares": total_cuotas_dolares,
            "total_corrientes_pesos": total_pesos - total_cuotas_pesos,
            "total_corrientes_dolares": total_dolares - total_cuotas_dolares,
            "porcentaje_cuotas_pesos": round(total_cuotas_pesos / total_pesos*100,2),
            "df_resumido": df_resumido,
            "df_cuotas_restantes": df_cuotas_restantes_html,
            "cuotas_restantes": df_cuotas_restantes['cuotas_restantes'].tolist(),
            "montos_cuotas_restantes": df_cuotas_restantes['saldo_mes'].tolist(),
            "nombre_archivo": nombre_archivo
        }


        return render_template("resultado.html", **contexto)
    except ValueError as e:
        return render_template("error.html", mensaje=str(e)), 400  # Error del cliente
    except Exception as e:
        return render_template("error.html", mensaje="Error inesperado: " + str(e)), 500  # Error del servidor