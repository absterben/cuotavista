from flask import Flask, render_template
from bancos.brou.routes import brou_bp
# from bancos.itau.routes import itau_bp

app = Flask(__name__)

# Registrar Blueprints
app.register_blueprint(brou_bp, url_prefix="/brou")
#app.register_blueprint(itau_bp, url_prefix="/itau")

@app.route("/")
def index():
    return render_template("principal.html")

@app.route("/brou")
def index_brou():
    return render_template("index_brou.html")

@app.route("/itau")
def index_itau():
    return render_template("index_itau.html")


if __name__ == "__main__":
    app.run(debug=True)
