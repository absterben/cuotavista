from flask import Blueprint, request, render_template
import pandas as pd
from bancos.brou.parser_caja_ahorro import depurar_archivo_pesos

bp_caja_ahorro = Blueprint("bp_caja_ahorro", __name__)

@bp_caja_ahorro.route("/caja_brou_resultado", methods=["POST"])
def resultado_caja_brou():
    if "archivos" not in request.files:
        return render_template("error.html", mensaje="No se subió ningún archivo"), 400

    archivos = request.files.getlist("archivos")
    dfs = []

    try:
        for archivo in archivos:
            df = depurar_archivo_pesos(archivo)
            dfs.append(df)

        if not dfs:
            return render_template("error.html", mensaje="No se pudieron procesar los archivos."), 400

        # Concatenar todos los DataFrames
        df = pd.concat(dfs, ignore_index=True)

        # Validar columnas
        if "Fecha" not in df.columns or "Débito" not in df.columns or "Crédito" not in df.columns:
            return render_template("error.html", mensaje="Faltan columnas 'Débito' o 'Crédito'"), 400

        # Procesar tipos de datos
        df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
        df = df.dropna(subset=["Fecha"]).sort_values("Fecha")

        df["Débito"] = pd.to_numeric(df["Débito"], errors="coerce").fillna(0)
        df["Crédito"] = pd.to_numeric(df["Crédito"], errors="coerce").fillna(0)

        # Calcular importe
        df["Importe"] = df["Crédito"] - df["Débito"]

        # Calcular totales
        ingresos = df[df["Importe"] > 0]["Importe"].sum()
        egresos = df[df["Importe"] < 0]["Importe"].sum()
        saldo_total = df["Importe"].sum()

        # Agrupación mensual para el gráfico
        df["Mes"] = df["Fecha"].dt.to_period("M")
        resumen_mensual = df.groupby("Mes").agg({
            "Crédito": "sum",
            "Débito": "sum"
        }).reset_index()

        resumen_mensual["Ingreso"] = resumen_mensual["Crédito"]
        resumen_mensual["Egreso"] = resumen_mensual["Débito"].abs()  # Mostrar egresos como positivos
        resumen_mensual["Mes"] = resumen_mensual["Mes"].astype(str)

        # Formato para movimientos detallados
        df["Fecha_formato"] = df["Fecha"].dt.strftime("%d/%m/%Y")
        movimientos = df[["Fecha_formato", "Descripción", "Débito", "Crédito", "Importe"]]
        movimientos = movimientos.rename(columns={"Fecha_formato": "Fecha"}).to_dict(orient="records")

        # Crear tabla pivote
        pivot = df.pivot_table(
            index="Descripción",
            columns=df["Fecha"].apply(lambda x: x.strftime("%b %Y")),
            values="Importe",
            aggfunc="sum",
            fill_value=0
        ).reset_index()

        # 🔥 Ordenar columnas de meses en orden cronológico
        columnas_meses = [col for col in pivot.columns if col != "Descripción"]
        columnas_meses_ordenadas = sorted(columnas_meses, key=lambda x: pd.to_datetime("01 " + x, dayfirst=True))
        pivot = pivot[["Descripción"] + columnas_meses_ordenadas]

        # Separar ingresos y egresos
        pivot_ingresos = pivot.copy()
        pivot_ingresos.iloc[:, 1:] = pivot_ingresos.iloc[:, 1:].applymap(lambda x: x if x > 0 else 0)

        pivot_egresos = pivot.copy()
        pivot_egresos.iloc[:, 1:] = pivot_egresos.iloc[:, 1:].applymap(lambda x: x if x < 0 else 0)

        # Función para detectar filas vacías
        def fila_todo_cero(row):
            return all(abs(row[col]) < 1e-5 for col in row.index if col != "Descripción")

        pivot_ingresos = pivot_ingresos[~pivot_ingresos.apply(fila_todo_cero, axis=1)]
        pivot_egresos = pivot_egresos[~pivot_egresos.apply(fila_todo_cero, axis=1)]

        # Ordenar por mayor monto absoluto
        def max_abs(row):
            return max(abs(row[col]) for col in row.index if col != "Descripción")

        pivot_ingresos["max_abs"] = pivot_ingresos.apply(max_abs, axis=1)
        pivot_ingresos = pivot_ingresos.sort_values("max_abs", ascending=False).drop(columns=["max_abs"])

        pivot_egresos["max_abs"] = pivot_egresos.apply(max_abs, axis=1)
        pivot_egresos = pivot_egresos.sort_values("max_abs", ascending=False).drop(columns=["max_abs"])

        # Convertir para el template
        tabla_ingresos = pivot_ingresos.to_dict(orient="records")
        tabla_egresos = pivot_egresos.to_dict(orient="records")
        columnas_tabla = ["Descripción"] + columnas_meses_ordenadas

        return render_template("resultado_caja_ahorro.html",
                                ingresos=ingresos,
                                egresos=egresos,
                                saldo_total=saldo_total,
                                resumen_mensual=resumen_mensual.to_dict(orient="records"),
                                movimientos=movimientos,
                                tabla_ingresos=tabla_ingresos,
                                tabla_egresos=tabla_egresos,
                                columnas_tabla=columnas_tabla)

    except Exception as e:
        return render_template("error.html", mensaje="Error procesando los datos: " + str(e)), 500
