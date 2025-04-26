import pandas as pd

def depurar_archivo_pesos(file):
    """
    Procesa un archivo Excel con movimientos de caja de ahorro del BROU
    y devuelve un DataFrame limpio con las columnas clave y el importe neto.
    Lanza excepciones si hay errores.
    """
    # Leer archivo según extensión
    if file.filename.endswith(".xls"):
        df = pd.read_excel(file, engine="xlrd")
    elif file.filename.endswith(".xlsx"):
        df = pd.read_excel(file, engine="openpyxl")
    else:
        raise ValueError("Formato de archivo no permitido (solo .xls o .xlsx)")

    # Buscar la segunda fila con "Fecha" como encabezado
    filas_fecha = df[df.apply(lambda x: x.astype(str).str.contains("Fecha", case=False, na=False)).any(axis=1)].index
    if len(filas_fecha) < 2:
        raise ValueError("No se encontró la fila adecuada para el encabezado")

    fila_encabezado = filas_fecha[1]
    df = df.iloc[fila_encabezado:].reset_index(drop=True)
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)

    # Eliminar filas y columnas vacías
    df = df.dropna(how="all").reset_index(drop=True)
    df = df.loc[:, df.notna().any(axis=0)]

    # Validar columnas clave
    columnas = ["Fecha", "Descripción", "Débito", "Crédito"]
    for col in columnas:
        if col not in df.columns:
            raise ValueError(f"Falta la columna '{col}' en el archivo")

    # Convertir fechas
    df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")

    # Convertir montos a numéricos
    df["Débito"] = pd.to_numeric(df["Débito"], errors="coerce").fillna(0)
    df["Crédito"] = pd.to_numeric(df["Crédito"], errors="coerce").fillna(0)

    # Calcular importe neto
    df["Importe"] = df["Crédito"] - df["Débito"]

    # Filtrar movimientos irrelevantes
    excluir = "saldo inicial|saldo final|total|resumen"
    df = df[~df["Descripción"].str.lower().str.contains(excluir, na=False)]

    return df
