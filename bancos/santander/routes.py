# bancos/santander/routes.py

from flask import Blueprint, request, render_template, jsonify, session
from bancos.santander.parser import (
    extraer_movimientos_desde_pdf,
    extraer_resumen,
    extraer_texto_completo,
    desencriptar_pdf,
    check_pdf_encrypted,
    PasswordRequiredError,
    InvalidPasswordError,
    InvalidPDFError,
    SantanderPDFError
)
from bancos.santander.utils import es_cuota, numero_cuotas
import pandas as pd
import os
import uuid
import time

santander_bp = Blueprint("santander", __name__)

# Almacenamiento temporal en memoria para PDFs pendientes de contraseña
_pending_pdfs = {}


def _cleanup_old_pending():
    """Limpia PDFs pendientes que tengan más de 5 minutos."""
    current_time = time.time()
    expired = [k for k, v in _pending_pdfs.items() if current_time - v['timestamp'] > 300]
    for k in expired:
        del _pending_pdfs[k]


@santander_bp.route("/upload", methods=["POST"])
def upload_santander():
    """
    Endpoint para subir PDF de Santander con auto-análisis.
    
    Flujo:
    1. Recibe archivo PDF
    2. Si NO está encriptado -> procesa directo y redirige
    3. Si está encriptado -> guarda temp_id y responde needs_password
    """
    _cleanup_old_pending()
    
    archivo = request.files.get("archivo")
    
    if not archivo:
        return jsonify({
            "success": False,
            "error_type": "no_file",
            "message": "No se subió ningún archivo."
        }), 400
    
    nombre_archivo = archivo.filename
    
    if not nombre_archivo.lower().endswith('.pdf'):
        return jsonify({
            "success": False,
            "error_type": "invalid_format",
            "message": "El archivo debe ser un PDF."
        }), 400
    
    try:
        file_bytes = archivo.read()
        
        if len(file_bytes) < 100:
            return jsonify({
                "success": False,
                "error_type": "empty_file",
                "message": "El archivo está vacío o es muy pequeño."
            }), 400
        
        # Verificar si está encriptado
        is_encrypted = check_pdf_encrypted(file_bytes)
        
        if is_encrypted:
            # Guardar en memoria temporal y solicitar contraseña
            temp_id = uuid.uuid4().hex
            _pending_pdfs[temp_id] = {
                'file_bytes': file_bytes,
                'filename': nombre_archivo,
                'timestamp': time.time()
            }
            
            return jsonify({
                "success": False,
                "needs_password": True,
                "temp_id": temp_id,
                "message": "El PDF requiere contraseña para continuar."
            }), 200
        
        # PDF no encriptado - procesar directamente
        return _procesar_y_renderizar(file_bytes, None, nombre_archivo)
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error_type": "unexpected",
            "message": f"Error al procesar: {str(e)}"
        }), 500


@santander_bp.route("/process-with-password", methods=["POST"])
def process_with_password():
    """Endpoint para procesar un PDF pendiente con contraseña."""
    _cleanup_old_pending()
    
    temp_id = request.form.get("temp_id", "").strip()
    password = request.form.get("password", "").strip()
    
    if not temp_id or temp_id not in _pending_pdfs:
        return jsonify({
            "success": False,
            "error_type": "expired",
            "message": "Sesión expirada. Subí el archivo de nuevo."
        }), 400
    
    if not password:
        return jsonify({
            "success": False,
            "error_type": "missing_password",
            "message": "Ingresá la contraseña."
        }), 400
    
    pending = _pending_pdfs[temp_id]
    file_bytes = pending['file_bytes']
    nombre_archivo = pending['filename']
    
    del _pending_pdfs[temp_id]
    
    return _procesar_y_renderizar(file_bytes, password, nombre_archivo)


def _procesar_y_renderizar(file_bytes: bytes, password: str, nombre_archivo: str):
    """Procesa el PDF y devuelve HTML renderizado o error JSON."""
    try:
        # Extraer movimientos (devuelve tuple: df, validacion)
        df, validacion = extraer_movimientos_desde_pdf(file_bytes, password)
        
        # Extraer resumen
        reader = desencriptar_pdf(file_bytes, password)
        texto = extraer_texto_completo(reader)
        resumen = extraer_resumen(texto)
        
        # Asegurar columnas numéricas
        df["Importe $"] = pd.to_numeric(df["Importe $"], errors="coerce").fillna(0)
        df["Importe U$S"] = pd.to_numeric(df["Importe U$S"], errors="coerce").fillna(0)
        
        # Detectar cuotas
        if len(df) > 0:
            df["cuotas_pagas"], df["cuotas_totales"] = zip(*df["Detalle"].apply(numero_cuotas))
            df["cuotas_restantes"] = df["cuotas_totales"] - df["cuotas_pagas"]
            df["es_cuota"] = df.apply(
                lambda row: "SI" if es_cuota(row["Detalle"]) and pd.notna(row["cuotas_restantes"]) and 0 <= row["cuotas_restantes"] <= 11 else "NO",
                axis=1
            )
        else:
            df["cuotas_pagas"] = []
            df["cuotas_totales"] = []
            df["cuotas_restantes"] = []
            df["es_cuota"] = []
        
        # Calcular totales
        df_gastos = df[df["Importe $"] > 0]
        df_devoluciones = df[df["Importe $"] < 0]
        
        total_devoluciones = abs(df_devoluciones["Importe $"].sum(skipna=True))
        
        total_cuotas_pesos = df_gastos.loc[df_gastos["es_cuota"] == "SI", "Importe $"].sum(skipna=True)
        total_cuotas_dolares = df_gastos.loc[df_gastos["es_cuota"] == "SI", "Importe U$S"].sum(skipna=True)
        total_corrientes_pesos = df_gastos.loc[df_gastos["es_cuota"] == "NO", "Importe $"].sum(skipna=True)
        total_corrientes_dolares = df_gastos.loc[df_gastos["es_cuota"] == "NO", "Importe U$S"].sum(skipna=True)
        
        # Total neto considera devoluciones
        total_pesos = total_cuotas_pesos + total_corrientes_pesos - total_devoluciones
        total_dolares = df_gastos["Importe U$S"].sum(skipna=True)
        
        porcentaje_cuotas_pesos = round((total_cuotas_pesos / (total_cuotas_pesos + total_corrientes_pesos)) * 100, 2) if (total_cuotas_pesos + total_corrientes_pesos) > 0 else 0

        # Incorporar saldo anterior al análisis (sin tratarlo como movimiento)
        saldo_anterior = resumen.get('saldo_anterior', 0) or 0
        total_pesos_con_saldo_anterior = total_pesos + saldo_anterior
        
        # Proyección de cuotas
        df_cuotas = df_gastos[df_gastos["es_cuota"] == "SI"].copy()
        
        if len(df_cuotas) > 0:
            df_cuotas_restantes = df_cuotas.groupby('cuotas_restantes', as_index=False)['Importe $'].sum()
            ultimo_mes = int(df_cuotas_restantes["cuotas_restantes"].max()) if len(df_cuotas_restantes) > 0 else 0
        else:
            df_cuotas_restantes = pd.DataFrame({'cuotas_restantes': [0], 'Importe $': [0]})
            ultimo_mes = 0
        
        meses_completos = pd.DataFrame({'cuotas_restantes': range(ultimo_mes + 1)})
        df_cuotas_restantes = meses_completos.merge(df_cuotas_restantes, on="cuotas_restantes", how="left").fillna(0)
        df_cuotas_restantes = df_cuotas_restantes.sort_values(by="cuotas_restantes", ascending=True)
        df_cuotas_restantes["saldo_mes"] = df_cuotas_restantes["Importe $"].iloc[::-1].cumsum().iloc[::-1]
        
        cuotas_mes_actual_df = df_gastos[
            (df_gastos["es_cuota"] == "SI") & (df_gastos["cuotas_pagas"] == 1)
        ] if len(df_gastos) > 0 else pd.DataFrame()
        
        cuotas_mes_actual_html = cuotas_mes_actual_df.fillna("").to_html(
            classes='min-w-full', index=True, na_rep=""
        ) if len(cuotas_mes_actual_df) > 0 else "<p>No hay cuotas nuevas este mes</p>"
        
        cuotas_mes_total_pesos = cuotas_mes_actual_df["Importe $"].sum(skipna=True) if len(cuotas_mes_actual_df) > 0 else 0
        cuotas_mes_total_dolares = cuotas_mes_actual_df["Importe U$S"].sum(skipna=True) if len(cuotas_mes_actual_df) > 0 else 0
        cuotas_mes_cantidad = len(cuotas_mes_actual_df)
        
        # Tabla HTML sin columnas auxiliares
        df_html = df.drop(columns=["cuotas_pagas", "cuotas_totales", "cuotas_restantes"], errors='ignore').fillna("")
        
        # Guardar Excel
        os.makedirs("archivos_temp", exist_ok=True)
        nombre_excel = f"{uuid.uuid4().hex}.xlsx"
        ruta_excel = os.path.join("archivos_temp", nombre_excel)
        df.to_excel(ruta_excel, index=False)
        
        cuotas_restantes_list = df_cuotas_restantes['cuotas_restantes'].tolist()
        montos_cuotas_restantes_list = df_cuotas_restantes['saldo_mes'].tolist()
        
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
            "total_pesos_con_saldo_anterior": round(total_pesos_con_saldo_anterior, 2),
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
            "nombre_banco": "Santander",
            "banco_color": "red",
            "saldo_anterior": saldo_anterior,
            "saldo_contado": resumen.get('saldo_contado', 0),
            "pago_minimo": resumen.get('pago_minimo', 0),
            "validacion_warning": validacion.get('warning'),
            "total_devoluciones": total_devoluciones,
        }
        
        return render_template("resultado.html", **contexto)
        
    except PasswordRequiredError:
        return jsonify({
            "success": False,
            "error_type": "password_required",
            "message": "El PDF requiere contraseña."
        }), 400
    
    except InvalidPasswordError:
        return jsonify({
            "success": False,
            "error_type": "invalid_password",
            "message": "Contraseña incorrecta."
        }), 400
    
    except InvalidPDFError:
        return jsonify({
            "success": False,
            "error_type": "invalid_pdf",
            "message": "Archivo inválido. Asegurate de subir un PDF válido de Santander."
        }), 400
    
    except SantanderPDFError as e:
        return jsonify({
            "success": False,
            "error_type": "pdf_error",
            "message": str(e)
        }), 400
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error_type": "unexpected",
            "message": f"Error inesperado: {str(e)}"
        }), 500


# Endpoint legacy para compatibilidad
@santander_bp.route("/resultado", methods=["POST"])
def procesar_pdf_santander_legacy():
    """Endpoint legacy - redirige al nuevo flujo."""
    return upload_santander()
