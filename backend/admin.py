import os
import re
import uuid
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, session, redirect, url_for, flash, request, current_app
from database import get_db
from utils.importers import analyze_publication_link, analyze_web_catalog

admin_routes = Blueprint("admin", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def es_admin():
    return session.get("role") == "admin"


def crear_slug(texto):
    texto = (texto or "").strip().lower()
    reemplazos = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"
    }
    for k, v in reemplazos.items():
        texto = texto.replace(k, v)
    texto = re.sub(r"[^a-z0-9]+", "-", texto)
    texto = texto.strip("-")
    return texto or "categoria"


def archivo_permitido(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def guardar_imagen_admin(file_storage):
    if not file_storage or not file_storage.filename:
        return ""

    if not archivo_permitido(file_storage.filename):
        return None

    filename_seguro = secure_filename(file_storage.filename)
    extension = filename_seguro.rsplit(".", 1)[1].lower()
    nuevo_nombre = f"{uuid.uuid4().hex}.{extension}"

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)

    ruta_completa = os.path.join(upload_folder, nuevo_nombre)
    file_storage.save(ruta_completa)

    return f"/static/uploads/{nuevo_nombre}"


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
        SELECT id, email, telefono, role, blocked, created_at
        FROM users
        ORDER BY id DESC
    """).fetchall()

    categorias = c.execute("""
        SELECT *
        FROM categories
        ORDER BY active DESC, nombre COLLATE NOCASE ASC
    """).fetchall()

    conn.close()

    return render_template("admin_dashboard.html", usuarios=usuarios, categorias=categorias)


@admin_routes.route("/admin/categories/create", methods=["POST"])
def create_category():
    if "user_id" not in session or not es_admin():
        flash("No tenés permisos para esta acción.", "danger")
        return redirect(url_for("auth.login"))

    nombre = request.form.get("nombre", "").strip()

    if not nombre:
        flash("Ingresá el nombre de la categoría.", "danger")
        return redirect(url_for("admin.admin_dashboard"))

    slug = crear_slug(nombre)

    conn = get_db()
    c = conn.cursor()

    existe = c.execute("""
        SELECT id FROM categories
        WHERE nombre = ? OR slug = ?
    """, (nombre, slug)).fetchone()

    if existe:
        conn.close()
        flash("Esa categoría ya existe.", "warning")
        return redirect(url_for("admin.admin_dashboard"))

    c.execute("""
        INSERT INTO categories (nombre, slug, active)
        VALUES (?, ?, 1)
    """, (nombre, slug))

    conn.commit()
    conn.close()

    flash("Categoría creada correctamente.", "success")
    return redirect(url_for("admin.admin_dashboard"))


@admin_routes.route("/admin/categories/<int:category_id>/toggle", methods=["POST"])
def toggle_category(category_id):
    if "user_id" not in session or not es_admin():
        flash("No tenés permisos para esta acción.", "danger")
        return redirect(url_for("auth.login"))

    conn = get_db()
    c = conn.cursor()

    categoria = c.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()

    if not categoria:
        conn.close()
        flash("Categoría no encontrada.", "danger")
        return redirect(url_for("admin.admin_dashboard"))

    nuevo_estado = 0 if categoria["active"] == 1 else 1

    c.execute("""
        UPDATE categories
        SET active = ?
        WHERE id = ?
    """, (nuevo_estado, category_id))

    conn.commit()
    conn.close()

    flash("Categoría actualizada.", "success")
    return redirect(url_for("admin.admin_dashboard"))


@admin_routes.route("/admin/categories/<int:category_id>/delete", methods=["POST"])
def delete_category(category_id):
    if "user_id" not in session or not es_admin():
        flash("No tenés permisos para esta acción.", "danger")
        return redirect(url_for("auth.login"))

    conn = get_db()
    c = conn.cursor()

    categoria = c.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()

    if not categoria:
        conn.close()
        flash("Categoría no encontrada.", "danger")
        return redirect(url_for("admin.admin_dashboard"))

    usados = c.execute("""
        SELECT COUNT(*) AS total
        FROM products
        WHERE tipo_publicacion = ?
    """, (categoria["slug"],)).fetchone()["total"]

    if usados > 0:
        conn.close()
        flash("No se puede eliminar porque ya tiene publicaciones. Podés desactivarla.", "warning")
        return redirect(url_for("admin.admin_dashboard"))

    c.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    conn.commit()
    conn.close()

    flash("Categoría eliminada.", "success")
    return redirect(url_for("admin.admin_dashboard"))


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
        SELECT id, email, telefono, role, blocked, tienda_nombre, ciudad, created_at
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
    if "user_id" not in session or not es_admin():
        flash("No tenés permisos para esta acción.", "danger")
        return redirect(url_for("auth.login"))

    if user_id == session.get("user_id"):
        flash("No podés bloquear tu propia cuenta.", "danger")
        return redirect(url_for("admin.admin_dashboard"))

    conn = get_db()
    c = conn.cursor()

    c.execute("UPDATE users SET blocked = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    flash("Usuario bloqueado correctamente.", "success")

    if request.args.get("next") == "detail":
        return redirect(url_for("admin.admin_user_detail", user_id=user_id))

    return redirect(url_for("admin.admin_dashboard"))


@admin_routes.route("/admin/user/<int:user_id>/unblock")
def unblock_user(user_id):
    if "user_id" not in session or not es_admin():
        flash("No tenés permisos para esta acción.", "danger")
        return redirect(url_for("auth.login"))

    conn = get_db()
    c = conn.cursor()

    c.execute("UPDATE users SET blocked = 0 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    flash("Usuario desbloqueado correctamente.", "success")

    if request.args.get("next") == "detail":
        return redirect(url_for("admin.admin_user_detail", user_id=user_id))

    return redirect(url_for("admin.admin_dashboard"))


@admin_routes.route("/admin/import-post", methods=["GET", "POST"])
def admin_import_post():
    if "user_id" not in session or not es_admin():
        flash("No tenés permisos para esta sección.", "danger")
        return redirect(url_for("auth.login"))

    extracted = None

    if request.method == "POST":
        action = request.form.get("action", "").strip()

        if action == "analyze":
            source_url = request.form.get("source_url", "").strip()
            source_type = request.form.get("source_type", "").strip()

            try:
                extracted = analyze_publication_link(source_url, source_type)
                flash("Link analizado correctamente.", "success")
            except Exception as e:
                flash(f"No se pudo analizar el link. Error: {str(e)}", "danger")

            return render_template("admin_import_post.html", extracted=extracted)

        if action == "publish":
            titulo = request.form.get("titulo", "").strip()
            descripcion = request.form.get("descripcion", "").strip()
            imagen = request.form.get("imagen", "").strip()
            tienda_nombre = request.form.get("tienda_nombre", "").strip()
            precio_raw = request.form.get("precio", "").strip()
            ciudad = request.form.get("ciudad", "").strip()
            whatsapp_link = request.form.get("whatsapp_link", "").strip()
            instagram_link = request.form.get("instagram_link", "").strip()
            facebook_link = request.form.get("facebook_link", "").strip()
            imagen_file = request.files.get("imagen_file")

            precio = 0
            if precio_raw:
                try:
                    precio = float(precio_raw.replace(".", "").replace(",", "."))
                except ValueError:
                    precio = 0

            if imagen_file and imagen_file.filename:
                imagen_subida = guardar_imagen_admin(imagen_file)
                if imagen_subida:
                    imagen = imagen_subida

            conn = get_db()
            c = conn.cursor()

            c.execute("""
                INSERT INTO products (
                    user_id, tipo_publicacion, rubro, titulo, descripcion, precio,
                    imagen, tienda_nombre, ciudad, whatsapp_link, instagram_link,
                    facebook_link, active, sold
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session["user_id"], "venta", "", titulo, descripcion, precio,
                imagen, tienda_nombre, ciudad, whatsapp_link, instagram_link,
                facebook_link, 1, 0
            ))

            conn.commit()
            conn.close()

            flash("Publicación importada correctamente.", "success")
            return redirect(url_for("admin.admin_import_post"))

    return render_template("admin_import_post.html", extracted=extracted)


@admin_routes.route("/admin/import-web", methods=["GET", "POST"])
def admin_import_web():
    if "user_id" not in session or not es_admin():
        flash("No tenés permisos para esta sección.", "danger")
        return redirect(url_for("auth.login"))

    extracted = None

    if request.method == "POST":
        action = request.form.get("action", "").strip()

        if action == "analyze":
            source_url = request.form.get("source_url", "").strip()

            try:
                extracted = analyze_web_catalog(source_url)
                flash("Web analizada correctamente.", "success")
            except Exception as e:
                flash(f"No se pudo analizar la web. Error: {str(e)}", "danger")

            return render_template("admin_import_web.html", extracted=extracted)

        if action == "publish_all":
            tienda_nombre = request.form.get("tienda_nombre", "").strip()
            ciudad = request.form.get("ciudad", "").strip()
            whatsapp_link = request.form.get("whatsapp_link", "").strip()
            instagram_link = request.form.get("instagram_link", "").strip()
            facebook_link = request.form.get("facebook_link", "").strip()

            titulos = request.form.getlist("producto_titulo[]")
            descripciones = request.form.getlist("producto_descripcion[]")
            precios_raw = request.form.getlist("producto_precio[]")
            imagenes = request.form.getlist("producto_imagen[]")
            links = request.form.getlist("producto_link[]")
            seleccionados = request.form.getlist("producto_selected[]")

            conn = get_db()
            c = conn.cursor()

            publicados = 0

            for i in range(len(titulos)):
                if str(i) not in seleccionados:
                    continue

                titulo = (titulos[i] or "").strip()
                descripcion = (descripciones[i] or "").strip()
                precio_raw = (precios_raw[i] or "").strip()
                imagen = (imagenes[i] or "").strip()
                link_origen = (links[i] or "").strip()

                precio = 0
                if precio_raw:
                    try:
                        precio = float(precio_raw.replace(".", "").replace(",", "."))
                    except ValueError:
                        precio = 0

                if link_origen:
                    descripcion += f"\n\nProducto original: {link_origen}"

                c.execute("""
                    INSERT INTO products (
                        user_id, tipo_publicacion, rubro, titulo, descripcion, precio,
                        imagen, tienda_nombre, ciudad, whatsapp_link, instagram_link,
                        facebook_link, active, sold
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session["user_id"], "venta", "", titulo, descripcion, precio,
                    imagen, tienda_nombre, ciudad, whatsapp_link, instagram_link,
                    facebook_link, 1, 0
                ))

                publicados += 1

            conn.commit()
            conn.close()

            flash(f"Se publicaron {publicados} productos.", "success")
            return redirect(url_for("admin.admin_import_web"))

    return render_template("admin_import_web.html", extracted=extracted)