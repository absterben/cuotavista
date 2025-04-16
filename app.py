from flask import Flask, render_template, send_file
from bancos.brou.routes import brou_bp
from bancos.itau.routes import itau_bp
import os
import tempfile
import pandas as pd
import threading

app = Flask(__name__)

# Registrar Blueprints
app.register_blueprint(brou_bp, url_prefix="/brou")
app.register_blueprint(itau_bp, url_prefix="/itau")

@app.route("/")
def index():
    return render_template("principal.html")

@app.route("/brou")
def index_brou():
    return render_template("index_brou.html")

@app.route("/descargar_excel/<nombre_archivo>")
def descargar_excel(nombre_archivo):
    ruta = os.path.join("archivos_temp", nombre_archivo)
    if not os.path.exists(ruta):
        return "Archivo no encontrado", 404

    # Preparo la respuesta
    response = send_file(ruta, as_attachment=True)

    # Defino función de eliminación con delay
    def eliminar_archivo():
        try:
            os.remove(ruta)
            print(f"Archivo eliminado correctamente: {ruta}")
        except Exception as e:
            print(f"Error al eliminar el archivo: {e}")

    # Espero 5 segundos para evitar problemas con bloqueo en Windows
    threading.Timer(5.0, eliminar_archivo).start()

    return response

@app.route("/mision_vision")
def index_mision_vision():
    return render_template("mision_vision.html")

@app.route("/itau")
def index_itau():
    return render_template("index_itau.html")




if __name__ == "__main__":
    app.run(debug=True)
