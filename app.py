from flask import Flask, render_template, request, jsonify, make_response, send_file
import pandas as pd
import os
import re
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder
import json
import pdfkit


app = Flask(__name__)

# Configurar carpeta de subida (desactivar para pruebas)
# UPLOAD_FOLDER = "uploads"
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Ruta principal
@app.route("/")
def index():
    return render_template("index.html")

'''

FUNCIONES PRINCIPALES DEL PROGRAMA


- Depurar archivo✔
- Calculo totales✔
- Clasificar cuotas✔
- Totales cuotas✔
- Categorización automática de gastos
- Ajuste manual de la categorización


- Hacer gráficos 
    -Pie chart por cuotas (cuota vs no cuota)
    -Pie chart por categorias (diferentes categorias)
    -Flujo en proximos meses

'''

def depurar_archivo(file):
    """
    Función para leer y depurar el archivo cargado.
    Retorna un DataFrame limpio.
    """
    try:
        # Leer el archivo con pandas según el tipo
        if file.filename.endswith(".xls"):  # Archivos Excel antiguos
            df = pd.read_excel(file, engine="xlrd")
        elif file.filename.endswith(".xlsx"):  # Archivos Excel modernos
            df = pd.read_excel(file, engine="openpyxl")
        else:
            return None, "Formato de archivo no permitido"

        # Encontrar la fila con el segundo "Fecha" como referencia del encabezado
        filas_fecha = df[df.apply(lambda x: x.astype(str).str.contains("Fecha", case=False, na=False)).any(axis=1)].index
        
        if len(filas_fecha) < 2:
            return None, "No se encontró la fila adecuada para el encabezado"

        fila_encabezado = filas_fecha[1]  # Segunda aparición de "Fecha"
        df = df.iloc[fila_encabezado:].reset_index(drop=True)
        df.columns = df.iloc[0]  # Asignar la primera fila como encabezado
        df = df[1:].reset_index(drop=True)  # Eliminar fila duplicada

        # Eliminar la última fila y las completamente vacías
        df = df.iloc[:-1]  
        df = df.dropna(how='all').reset_index(drop=True)

        # Eliminar columnas completamente vacías, excepto "Importe Origen"
        df = df.loc[:, (df.notna().any(axis=0)) | (df.columns == "Importe Origen")]

        # Validar si la columna "Importe $" existe antes de continuar
        if "Importe $" not in df.columns:
            return None, "No se encontró la columna 'Importe $' en el archivo"

        # Convertir "Importe $" a valores numéricos
        df["Importe $"] = (
            df["Importe $"]
            .fillna("")
            .astype(str)
            .str.replace(".", "", regex=False)  # Eliminar puntos (separadores de miles)
            .str.replace(",", ".", regex=False)  # Reemplazar comas por puntos
            .apply(pd.to_numeric, errors="coerce")  # Convertir a float
        )

        # Convertir "Importe U$S" a valores numéricos
        df["Importe U$S"] = (
            df["Importe U$S"]
            .fillna("")
            .astype(str)
            .str.replace(".", "", regex=False)  # Eliminar puntos (separadores de miles)
            .str.replace(",", ".", regex=False)  # Reemplazar comas por puntos
            .apply(pd.to_numeric, errors="coerce")  # Convertir a float
        )    

        return df

    except Exception as e:
        return None, e


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

'''

FIN DE LAS FUNCIONES 

'''

#
# PARA CREAR LA PAGINA DE RESULTADOS
#

@app.route("/resultado", methods=["POST"])
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

        # Crear tabla con los datos crudos.
        data_html = df.to_html(index=False, na_rep="")

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
    
        
if __name__ == "__main__":
    app.run(debug=True)
