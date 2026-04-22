# =========================================================
# PANEL ADMINISTRADOR
# =========================================================
# Permite:
# - ver usuarios registrados
# - bloquear usuarios
# - desbloquear usuarios
# - ver detalle de un vendedor
# - ver y gestionar productos de un vendedor
# =========================================================

from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from database import get_db

admin_routes = Blueprint("admin", __name__)


def es_admin():
    return session.get("role") == "admin"


@admin_routes.route("/admin/dashboard")
def admin_dashboard():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if not es_admin():
        flash("No tenés permisos para entrar al panel administrador.", "danger")
        return redirect(url_for("products.seller_dashboard"))

    conn = get_db()
    c = conn.cursor()

    usuarios = c.execute("""
        SELECT
            id,
            email,
            telefono,
            role,
            blocked,
            created_at
        FROM users
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template("admin_dashboard.html", usuarios=usuarios)


@admin_routes.route("/admin/user/<int:user_id>")
def admin_user_detail(user_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if not es_admin():
        flash("No tenés permisos para entrar a esta sección.", "danger")
        return redirect(url_for("products.seller_dashboard"))

    conn = get_db()
    c = conn.cursor()

    usuario = c.execute("""
        SELECT
            id,
            email,
            telefono,
            role,
            blocked,
            tienda_nombre,
            ciudad,
            created_at
        FROM users
        WHERE id = ?
    """, (user_id,)).fetchone()

    if not usuario:
        conn.close()
        flash("Usuario no encontrado.", "danger")
        return redirect(url_for("admin.admin_dashboard"))

    publicaciones = c.execute("""
        SELECT *
        FROM products
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,)).fetchall()

    conn.close()

    return render_template("admin_user_detail.html", usuario=usuario, publicaciones=publicaciones)


@admin_routes.route("/admin/user/<int:user_id>/block")
def block_user(user_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if not es_admin():
        flash("No tenés permisos para esta acción.", "danger")
        return redirect(url_for("products.seller_dashboard"))

    if user_id == session.get("user_id"):
        flash("No podés bloquear tu propia cuenta.", "danger")
        return redirect(url_for("admin.admin_dashboard"))

    conn = get_db()
    c = conn.cursor()

    usuario = c.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()

    if not usuario:
        conn.close()
        flash("Usuario no encontrado.", "danger")
        return redirect(url_for("admin.admin_dashboard"))

    c.execute("""
        UPDATE users
        SET blocked = 1
        WHERE id = ?
    """, (user_id,))

    conn.commit()
    conn.close()

    flash("Usuario bloqueado correctamente.", "success")

    next_url = request.args.get("next")
    if next_url == "detail":
        return redirect(url_for("admin.admin_user_detail", user_id=user_id))

    return redirect(url_for("admin.admin_dashboard"))


@admin_routes.route("/admin/user/<int:user_id>/unblock")
def unblock_user(user_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if not es_admin():
        flash("No tenés permisos para esta acción.", "danger")
        return redirect(url_for("products.seller_dashboard"))

    conn = get_db()
    c = conn.cursor()

    usuario = c.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()

    if not usuario:
        conn.close()
        flash("Usuario no encontrado.", "danger")
        return redirect(url_for("admin.admin_dashboard"))

    c.execute("""
        UPDATE users
        SET blocked = 0
        WHERE id = ?
    """, (user_id,))

    conn.commit()
    conn.close()

    flash("Usuario desbloqueado correctamente.", "success")

    next_url = request.args.get("next")
    if next_url == "detail":
        return redirect(url_for("admin.admin_user_detail", user_id=user_id))

    return redirect(url_for("admin.admin_dashboard"))