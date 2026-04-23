# =========================================================
# PRODUCTOS - INICIO + PANEL VENDEDOR
# =========================================================

import os
import re
import uuid
from werkzeug.utils import secure_filename
from flask import Blueprint, jsonify, render_template, request, redirect, url_for, session, flash, current_app
from database import get_db

product_routes = Blueprint("products", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def usuario_logueado():
    return "user_id" in session


def puede_tocar_producto(producto, user_id, role):
    if role == "admin":
        return True
    return producto["user_id"] == user_id


def archivo_permitido(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def guardar_imagen(file_storage):
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


def limpiar_numero(numero):
    if not numero:
        return ""
    return re.sub(r"\D", "", numero)


def numero_a_whatsapp_link(numero):
    numero_limpio = limpiar_numero(numero)

    if not numero_limpio:
        return ""

    return f"https://wa.me/{numero_limpio}"


def whatsapp_link_a_numero(link_o_numero):
    if not link_o_numero:
        return ""

    if "wa.me/" in link_o_numero:
        return link_o_numero.split("wa.me/")[-1].strip()

    return limpiar_numero(link_o_numero)


@product_routes.route("/api/products", methods=["GET"])
def list_products():
    conn = get_db()
    c = conn.cursor()

    rows = c.execute("""
        SELECT
            id,
            titulo,
            descripcion,
            precio,
            imagen,
            tienda_nombre,
            ciudad,
            whatsapp_link,
            instagram_link,
            facebook_link
        FROM products
        ORDER BY precio ASC, id DESC
    """).fetchall()

    conn.close()

    productos = []
    for row in rows:
        productos.append({
            "id": row["id"],
            "titulo": row["titulo"] or "",
            "descripcion": row["descripcion"] or "",
            "precio": float(row["precio"]) if row["precio"] is not None else 0,
            "imagen": row["imagen"] or "",
            "tienda_nombre": row["tienda_nombre"] or "",
            "ciudad": row["ciudad"] or "",
            "whatsapp_link": row["whatsapp_link"] or "",
            "instagram_link": row["instagram_link"] or "",
            "facebook_link": row["facebook_link"] or ""
        })

    return jsonify(productos)


@product_routes.route("/api/cities", methods=["GET"])
def list_cities():
    conn = get_db()
    c = conn.cursor()

    rows = c.execute("""
        SELECT DISTINCT ciudad
        FROM products
        WHERE ciudad IS NOT NULL
          AND TRIM(ciudad) <> ''
        ORDER BY ciudad COLLATE NOCASE ASC
    """).fetchall()

    conn.close()

    ciudades = [row["ciudad"] for row in rows]
    return jsonify(ciudades)


@product_routes.route("/seller/dashboard", methods=["GET", "POST"])
def seller_dashboard():
    if not usuario_logueado():
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        tienda_nombre = request.form.get("tienda_nombre", "").strip()
        titulo = request.form.get("titulo", "").strip()
        descripcion = request.form.get("descripcion", "").strip()

        precio_raw = request.form.get("precio", "").strip()
        precio_limpio = precio_raw.replace(".", "").replace(",", ".")

        ciudad = request.form.get("ciudad", "").strip()

        whatsapp_numero = request.form.get("whatsapp_link", "").strip()
        instagram_link = request.form.get("instagram_link", "").strip()
        facebook_link = request.form.get("facebook_link", "").strip()

        imagen_file = request.files.get("imagen")

        if not tienda_nombre:
            flash("Ingresá el nombre de tu tienda o empresa.", "danger")
            return redirect(url_for("products.seller_dashboard"))

        if not titulo or not precio_limpio or not ciudad:
            flash("Completá título, precio y ciudad.", "danger")
            return redirect(url_for("products.seller_dashboard"))

        try:
            precio = float(precio_limpio)
            if precio <= 0:
                raise ValueError
        except ValueError:
            flash("El precio debe ser un número válido mayor a 0.", "danger")
            return redirect(url_for("products.seller_dashboard"))

        whatsapp_link = numero_a_whatsapp_link(whatsapp_numero)

        imagen = ""
        if imagen_file and imagen_file.filename:
            imagen = guardar_imagen(imagen_file)
            if imagen is None:
                flash("La imagen debe ser PNG, JPG, JPEG o WEBP.", "danger")
                return redirect(url_for("products.seller_dashboard"))

        conn = get_db()
        c = conn.cursor()

        c.execute("""
            UPDATE users
            SET tienda_nombre = ?, ciudad = ?
            WHERE id = ?
        """, (tienda_nombre, ciudad, session["user_id"]))

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
                facebook_link
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            titulo,
            descripcion,
            precio,
            imagen,
            tienda_nombre,
            ciudad,
            whatsapp_link,
            instagram_link,
            facebook_link
        ))

        conn.commit()
        conn.close()

        session["tienda_nombre"] = tienda_nombre
        session["ciudad"] = ciudad

        flash("Producto publicado correctamente.", "success")
        return redirect(url_for("products.seller_dashboard"))

    conn = get_db()
    c = conn.cursor()

    publicaciones = c.execute("""
        SELECT *
        FROM products
        WHERE user_id = ?
        ORDER BY id DESC
    """, (session["user_id"],)).fetchall()

    user = c.execute("""
        SELECT tienda_nombre, ciudad
        FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    conn.close()

    return render_template("seller_dashboard.html", publicaciones=publicaciones, user=user)


@product_routes.route("/seller/product/<int:product_id>/edit", methods=["GET", "POST"])
def edit_product(product_id):
    if not usuario_logueado():
        return redirect(url_for("auth.login"))

    conn = get_db()
    c = conn.cursor()

    producto = c.execute("""
        SELECT *
        FROM products
        WHERE id = ?
    """, (product_id,)).fetchone()

    if not producto:
        conn.close()
        flash("Producto no encontrado.", "danger")
        return redirect(url_for("products.seller_dashboard"))

    if not puede_tocar_producto(producto, session["user_id"], session["role"]):
        conn.close()
        flash("No podés editar este producto.", "danger")
        return redirect(url_for("products.seller_dashboard"))

    if request.method == "POST":
        tienda_nombre = request.form.get("tienda_nombre", "").strip()
        titulo = request.form.get("titulo", "").strip()
        descripcion = request.form.get("descripcion", "").strip()

        precio_raw = request.form.get("precio", "").strip()
        precio_limpio = precio_raw.replace(".", "").replace(",", ".")

        ciudad = request.form.get("ciudad", "").strip()

        whatsapp_numero = request.form.get("whatsapp_link", "").strip()
        instagram_link = request.form.get("instagram_link", "").strip()
        facebook_link = request.form.get("facebook_link", "").strip()

        imagen_actual = request.form.get("imagen_actual", "").strip()
        imagen_file = request.files.get("imagen")

        if not tienda_nombre:
            conn.close()
            flash("Ingresá el nombre de tu tienda o empresa.", "danger")
            return redirect(url_for("products.edit_product", product_id=product_id))

        if not titulo or not precio_limpio or not ciudad:
            conn.close()
            flash("Completá título, precio y ciudad.", "danger")
            return redirect(url_for("products.edit_product", product_id=product_id))

        try:
            precio = float(precio_limpio)
            if precio <= 0:
                raise ValueError
        except ValueError:
            conn.close()
            flash("El precio debe ser un número válido mayor a 0.", "danger")
            return redirect(url_for("products.edit_product", product_id=product_id))

        whatsapp_link = numero_a_whatsapp_link(whatsapp_numero)

        imagen = imagen_actual
        if imagen_file and imagen_file.filename:
            nueva_imagen = guardar_imagen(imagen_file)
            if nueva_imagen is None:
                conn.close()
                flash("La imagen debe ser PNG, JPG, JPEG o WEBP.", "danger")
                return redirect(url_for("products.edit_product", product_id=product_id))
            imagen = nueva_imagen

        c.execute("""
            UPDATE products
            SET
                titulo = ?,
                descripcion = ?,
                precio = ?,
                imagen = ?,
                tienda_nombre = ?,
                ciudad = ?,
                whatsapp_link = ?,
                instagram_link = ?,
                facebook_link = ?
            WHERE id = ?
        """, (
            titulo,
            descripcion,
            precio,
            imagen,
            tienda_nombre,
            ciudad,
            whatsapp_link,
            instagram_link,
            facebook_link,
            product_id
        ))

        if producto["user_id"] == session["user_id"]:
            c.execute("""
                UPDATE users
                SET tienda_nombre = ?, ciudad = ?
                WHERE id = ?
            """, (tienda_nombre, ciudad, session["user_id"]))
            session["tienda_nombre"] = tienda_nombre
            session["ciudad"] = ciudad

        conn.commit()
        conn.close()

        flash("Producto editado correctamente.", "success")

        if session["role"] == "admin" and producto["user_id"] != session["user_id"]:
            return redirect(url_for("admin.admin_user_detail", user_id=producto["user_id"]))

        return redirect(url_for("products.seller_dashboard"))

    producto_dict = dict(producto)
    producto_dict["whatsapp_numero"] = whatsapp_link_a_numero(producto["whatsapp_link"] or "")

    conn.close()
    return render_template("edit_product.html", producto=producto_dict)


@product_routes.route("/seller/product/<int:product_id>/delete", methods=["POST"])
def delete_product(product_id):
    if not usuario_logueado():
        return redirect(url_for("auth.login"))

    conn = get_db()
    c = conn.cursor()

    producto = c.execute("""
        SELECT *
        FROM products
        WHERE id = ?
    """, (product_id,)).fetchone()

    if not producto:
        conn.close()
        flash("Producto no encontrado.", "danger")
        return redirect(url_for("products.seller_dashboard"))

    if not puede_tocar_producto(producto, session["user_id"], session["role"]):
        conn.close()
        flash("No podés eliminar este producto.", "danger")
        return redirect(url_for("products.seller_dashboard"))

    # ELIMINACIÓN REAL
    c.execute("""
        DELETE FROM products
        WHERE id = ?
    """, (product_id,))

    conn.commit()
    conn.close()

    flash("Producto eliminado correctamente.", "success")

    if session["role"] == "admin" and producto["user_id"] != session["user_id"]:
        return redirect(url_for("admin.admin_user_detail", user_id=producto["user_id"]))

    return redirect(url_for("products.seller_dashboard"))


@product_routes.route("/seller/product/<int:product_id>/sold", methods=["POST"])
def mark_as_sold(product_id):
    if not usuario_logueado():
        return redirect(url_for("auth.login"))

    conn = get_db()
    c = conn.cursor()

    producto = c.execute("""
        SELECT *
        FROM products
        WHERE id = ?
    """, (product_id,)).fetchone()

    if not producto:
        conn.close()
        flash("Producto no encontrado.", "danger")
        return redirect(url_for("products.seller_dashboard"))

    if not puede_tocar_producto(producto, session["user_id"], session["role"]):
        conn.close()
        flash("No podés marcar este producto como vendido.", "danger")
        return redirect(url_for("products.seller_dashboard"))

    # si querés también podría borrarlo, pero lo dejamos como vendido
    c.execute("""
        UPDATE products
        SET sold = 1
        WHERE id = ?
    """, (product_id,))

    conn.commit()
    conn.close()

    flash("Producto marcado como vendido.", "success")

    if session["role"] == "admin" and producto["user_id"] != session["user_id"]:
        return redirect(url_for("admin.admin_user_detail", user_id=producto["user_id"]))

    return redirect(url_for("products.seller_dashboard"))


@product_routes.route("/seller/products/bulk-action", methods=["POST"])
def bulk_action_products():
    if not usuario_logueado():
        return redirect(url_for("auth.login"))

    product_ids = request.form.getlist("product_ids[]")
    bulk_action = request.form.get("bulk_action", "").strip()
    return_to = request.form.get("return_to", "").strip()
    owner_user_id = request.form.get("owner_user_id", "").strip()

    if not product_ids:
        flash("Seleccioná al menos un producto.", "warning")
        if return_to == "admin_detail" and owner_user_id:
            return redirect(url_for("admin.admin_user_detail", user_id=owner_user_id))
        return redirect(url_for("products.seller_dashboard"))

    if bulk_action not in ["delete", "sold"]:
        flash("Acción masiva no válida.", "danger")
        if return_to == "admin_detail" and owner_user_id:
            return redirect(url_for("admin.admin_user_detail", user_id=owner_user_id))
        return redirect(url_for("products.seller_dashboard"))

    conn = get_db()
    c = conn.cursor()

    afectados = 0

    for pid in product_ids:
        try:
            pid_int = int(pid)
        except ValueError:
            continue

        producto = c.execute("""
            SELECT *
            FROM products
            WHERE id = ?
        """, (pid_int,)).fetchone()

        if not producto:
            continue

        if not puede_tocar_producto(producto, session["user_id"], session["role"]):
            continue

        if bulk_action == "delete":
            # ELIMINACIÓN REAL
            c.execute("""
                DELETE FROM products
                WHERE id = ?
            """, (pid_int,))
            afectados += 1

        elif bulk_action == "sold":
            c.execute("""
                UPDATE products
                SET sold = 1
                WHERE id = ?
            """, (pid_int,))
            afectados += 1

    conn.commit()
    conn.close()

    if bulk_action == "delete":
        flash(f"Se eliminaron {afectados} productos.", "success")
    elif bulk_action == "sold":
        flash(f"Se marcaron {afectados} productos como vendidos.", "success")

    if return_to == "admin_detail" and owner_user_id:
        return redirect(url_for("admin.admin_user_detail", user_id=owner_user_id))

    return redirect(url_for("products.seller_dashboard"))