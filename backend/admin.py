# =========================================================
# PANEL ADMINISTRADOR
# =========================================================

import os
import uuid
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, session, redirect, url_for, flash, request, current_app
from database import get_db
from utils.importers import analyze_publication_link, analyze_web_catalog

admin_routes = Blueprint("admin", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def es_admin():
    return session.get("role") == "admin"


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


@admin_routes.route("/admin/import-post", methods=["GET", "POST"])
def admin_import_post():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if not es_admin():
        flash("No tenés permisos para esta sección.", "danger")
        return redirect(url_for("products.seller_dashboard"))

    extracted = None

    if request.method == "POST":
        action = request.form.get("action", "").strip()

        if action == "analyze":
            source_url = request.form.get("source_url", "").strip()
            source_type = request.form.get("source_type", "").strip()

            if not source_url:
                flash("Pegá un link para analizar.", "danger")
                return render_template("admin_import_post.html", extracted=None)

            try:
                extracted = analyze_publication_link(source_url, source_type)
                flash("Link analizado correctamente. Revisá y corregí antes de publicar.", "success")
            except Exception as e:
                flash(f"No se pudo analizar el link. Error: {str(e)}", "danger")
                return render_template("admin_import_post.html", extracted=None)

            return render_template("admin_import_post.html", extracted=extracted)

        if action == "publish":
            source_type = request.form.get("source_type", "").strip()
            source_url = request.form.get("source_url", "").strip()
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

            if not titulo:
                flash("El título es obligatorio.", "danger")
                extracted = request.form.to_dict()
                return render_template("admin_import_post.html", extracted=extracted)

            if not tienda_nombre:
                flash("El nombre de la tienda o usuario es obligatorio.", "danger")
                extracted = request.form.to_dict()
                return render_template("admin_import_post.html", extracted=extracted)

            if not ciudad:
                flash("La ciudad es obligatoria.", "danger")
                extracted = request.form.to_dict()
                return render_template("admin_import_post.html", extracted=extracted)

            precio = 0
            if precio_raw:
                try:
                    precio = float(precio_raw.replace(".", "").replace(",", "."))
                except ValueError:
                    flash("El precio no tiene un formato válido.", "danger")
                    extracted = request.form.to_dict()
                    return render_template("admin_import_post.html", extracted=extracted)

            descripcion_final = descripcion.strip()

            if source_url:
                if source_type == "instagram" and not instagram_link:
                    instagram_link = source_url
                elif source_type == "facebook" and not facebook_link:
                    facebook_link = source_url

            if imagen_file and imagen_file.filename:
                imagen_subida = guardar_imagen_admin(imagen_file)
                if imagen_subida is None:
                    flash("La imagen debe ser PNG, JPG, JPEG o WEBP.", "danger")
                    extracted = request.form.to_dict()
                    return render_template("admin_import_post.html", extracted=extracted)
                imagen = imagen_subida

            conn = get_db()
            c = conn.cursor()

            c.execute("""
                INSERT INTO products (
                    user_id,
                    titulo,
                    descripcion,
                    precio,
                    imagen,
                    tienda_nombre,
                    ciudad,
                    whatsapp_link,
                    instagram_link,
                    facebook_link,
                    active,
                    sold
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session["user_id"],
                titulo,
                descripcion_final,
                precio,
                imagen,
                tienda_nombre,
                ciudad,
                whatsapp_link,
                instagram_link,
                facebook_link,
                1,
                0
            ))

            conn.commit()
            conn.close()

            flash("Publicación importada y publicada correctamente.", "success")
            return redirect(url_for("admin.admin_import_post"))

    return render_template("admin_import_post.html", extracted=extracted)


@admin_routes.route("/admin/import-web", methods=["GET", "POST"])
def admin_import_web():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if not es_admin():
        flash("No tenés permisos para esta sección.", "danger")
        return redirect(url_for("products.seller_dashboard"))

    extracted = None

    if request.method == "POST":
        action = request.form.get("action", "").strip()

        # =====================================================
        # ANALIZAR WEB
        # =====================================================
        if action == "analyze":
            source_url = request.form.get("source_url", "").strip()

            if not source_url:
                flash("Pegá una URL de página web.", "danger")
                return render_template("admin_import_web.html", extracted=None)

            try:
                extracted = analyze_web_catalog(source_url)
                if not extracted.get("products"):
                    flash("La web se analizó, pero no se pudieron detectar productos claros.", "warning")
                else:
                    flash(f"Se detectaron {len(extracted.get('products', []))} productos. Revisá y publicá.", "success")
            except Exception as e:
                flash(f"No se pudo analizar la web. Error: {str(e)}", "danger")
                return render_template("admin_import_web.html", extracted=None)

            return render_template("admin_import_web.html", extracted=extracted)

        # =====================================================
        # PUBLICAR TODOS LOS SELECCIONADOS
        # =====================================================
        if action == "publish_all":
            source_url = request.form.get("source_url", "").strip()
            tienda_nombre = request.form.get("tienda_nombre", "").strip()
            ciudad = request.form.get("ciudad", "").strip()
            whatsapp_link = request.form.get("whatsapp_link", "").strip()
            instagram_link = request.form.get("instagram_link", "").strip()
            facebook_link = request.form.get("facebook_link", "").strip()

            if not tienda_nombre:
                flash("El nombre de la tienda es obligatorio.", "danger")
                extracted = request.form.to_dict(flat=False)
                return render_template("admin_import_web.html", extracted=None)

            if not ciudad:
                flash("La ciudad es obligatoria.", "danger")
                extracted = request.form.to_dict(flat=False)
                return render_template("admin_import_web.html", extracted=None)

            titulos = request.form.getlist("producto_titulo[]")
            descripciones = request.form.getlist("producto_descripcion[]")
            precios_raw = request.form.getlist("producto_precio[]")
            imagenes = request.form.getlist("producto_imagen[]")
            links = request.form.getlist("producto_link[]")
            seleccionados = request.form.getlist("producto_selected[]")

            if not titulos:
                flash("No hay productos para publicar.", "danger")
                return redirect(url_for("admin.admin_import_web"))

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

                if not titulo:
                    continue

                precio = 0
                if precio_raw:
                    try:
                        precio = float(precio_raw.replace(".", "").replace(",", "."))
                    except ValueError:
                        precio = 0

                descripcion_final = descripcion
                if link_origen:
                    if descripcion_final:
                        descripcion_final += f"\n\nProducto original: {link_origen}"
                    else:
                        descripcion_final = f"Producto original: {link_origen}"

                c.execute("""
                    INSERT INTO products (
                        user_id,
                        titulo,
                        descripcion,
                        precio,
                        imagen,
                        tienda_nombre,
                        ciudad,
                        whatsapp_link,
                        instagram_link,
                        facebook_link,
                        active,
                        sold
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session["user_id"],
                    titulo,
                    descripcion_final,
                    precio,
                    imagen,
                    tienda_nombre,
                    ciudad,
                    whatsapp_link,
                    instagram_link,
                    facebook_link,
                    1,
                    0
                ))

                publicados += 1

            conn.commit()
            conn.close()

            flash(f"Se publicaron {publicados} productos en OFERTAS SANTIAGO.", "success")
            return redirect(url_for("admin.admin_import_web"))

    return render_template("admin_import_web.html", extracted=extracted)