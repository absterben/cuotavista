from flask import Flask, render_template, send_file
from bancos.brou.routes import brou_bp
from bancos.itau.routes import itau_bp
from bancos.santander.routes import santander_bp
import os
import threading

app = Flask(__name__)

# Registrar Blueprints
app.register_blueprint(brou_bp, url_prefix="/brou")
app.register_blueprint(itau_bp, url_prefix="/itau")
app.register_blueprint(santander_bp, url_prefix="/santander")


@app.route("/")
def index():
    return render_template("landing.html")


@app.route("/descargar_excel/<nombre_archivo>")
def descargar_excel(nombre_archivo):
    ruta = os.path.join("archivos_temp", nombre_archivo)
    if not os.path.exists(ruta):
        return "Archivo no encontrado", 404

    response = send_file(ruta, as_attachment=True)

    def eliminar_archivo():
        try:
            os.remove(ruta)
        except Exception as e:
            print(f"Error al eliminar archivo: {e}")

    # Delay para evitar problemas de bloqueo en Windows
    threading.Timer(5.0, eliminar_archivo).start()

    return response


if __name__ == "__main__":
    app.run(debug=True)
