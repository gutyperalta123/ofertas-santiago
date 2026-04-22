# =========================================================
# AUTENTICACIÓN - VENDEDORES Y ADMIN
# =========================================================

import re
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db

auth_routes = Blueprint("auth", __name__)


EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_REGEX = re.compile(r"^\+?\d{8,15}$")


def email_valido(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email))


def telefono_valido(telefono: str) -> bool:
    telefono_limpio = telefono.replace(" ", "").replace("-", "")
    return bool(PHONE_REGEX.match(telefono_limpio))


def password_valida(password: str):
    if len(password) < 8:
        return False, "La contraseña debe tener al menos 8 caracteres."
    if not re.search(r"[A-ZÁÉÍÓÚÑ]", password):
        return False, "La contraseña debe tener al menos una letra mayúscula."
    if not re.search(r"[a-záéíóúñ]", password):
        return False, "La contraseña debe tener al menos una letra minúscula."
    if not re.search(r"\d", password):
        return False, "La contraseña debe tener al menos un número."
    return True, ""


def verificar_password(password_guardada: str, password_ingresada: str) -> bool:
    if not password_guardada:
        return False

    # Compatibilidad con tu admin actual en texto plano
    if password_guardada == password_ingresada:
        return True

    # Compatibilidad con usuarios nuevos en hash
    if password_guardada.startswith("scrypt:") or password_guardada.startswith("pbkdf2:"):
        return check_password_hash(password_guardada, password_ingresada)

    return False


@auth_routes.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        acceso = request.form.get("acceso", "").strip()
        password = request.form.get("password", "").strip()

        if not acceso or not password:
            flash("Completá email o teléfono y contraseña.", "danger")
            return render_template("login.html")

        conn = get_db()
        c = conn.cursor()

        user = c.execute("""
            SELECT *
            FROM users
            WHERE email = ? OR telefono = ?
        """, (acceso.lower(), acceso)).fetchone()

        conn.close()

        if not user:
            flash("No existe una cuenta con ese email o teléfono.", "danger")
            return render_template("login.html")

        if user["blocked"] == 1:
            flash("Tu cuenta se encuentra bloqueada.", "danger")
            return render_template("login.html")

        if not verificar_password(user["password"], password):
            flash("La contraseña no es válida.", "danger")
            return render_template("login.html")

        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["email"] = user["email"]
        session["telefono"] = user["telefono"]
        session["tienda_nombre"] = user["tienda_nombre"]
        session["ciudad"] = user["ciudad"]

        # Si es admin, entra al panel admin
        if user["role"] == "admin":
            return redirect(url_for("admin.admin_dashboard"))

        return redirect(url_for("products.seller_dashboard"))

    return render_template("login.html")


@auth_routes.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        telefono = request.form.get("telefono", "").strip()
        password = request.form.get("password", "").strip()

        if not email or not telefono or not password:
            flash("Completá todos los campos.", "danger")
            return render_template("register.html")

        if not email_valido(email):
            flash("El email no es válido.", "danger")
            return render_template("register.html")

        if not telefono_valido(telefono):
            flash("El teléfono no es válido. Ingresalo con números reales.", "danger")
            return render_template("register.html")

        ok_password, msg_password = password_valida(password)
        if not ok_password:
            flash(msg_password, "danger")
            return render_template("register.html")

        conn = get_db()
        c = conn.cursor()

        existe_email = c.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        existe_telefono = c.execute("SELECT id FROM users WHERE telefono = ?", (telefono,)).fetchone()

        if existe_email:
            conn.close()
            flash("Ese email ya está registrado.", "danger")
            return render_template("register.html")

        if existe_telefono:
            conn.close()
            flash("Ese teléfono ya está registrado.", "danger")
            return render_template("register.html")

        password_hash = generate_password_hash(password)

        c.execute("""
            INSERT INTO users (
                email, telefono, password, tienda_nombre, ciudad, role, blocked
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            email,
            telefono,
            password_hash,
            "",
            "",
            "seller",
            0
        ))

        conn.commit()
        conn.close()

        flash("Cuenta creada correctamente. Ahora iniciá sesión.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_routes.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))