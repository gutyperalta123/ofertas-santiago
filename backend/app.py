# =========================================================
# APP PRINCIPAL - OFERTAS SANTIAGO
# =========================================================

import os
from flask import Flask, render_template
from flask_cors import CORS

from database import init_db
from products import product_routes
from auth import auth_routes
from admin import admin_routes

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)

app.secret_key = "ofertas_santiago_clave"
app.config["UPLOAD_FOLDER"] = os.path.join(app.static_folder, "uploads")

CORS(app)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

init_db()

app.register_blueprint(product_routes)
app.register_blueprint(auth_routes)
app.register_blueprint(admin_routes)


@app.route("/")
def home():
    return render_template("index.html")




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)