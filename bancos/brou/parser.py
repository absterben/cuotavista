import pandas as pd
import re
import os

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