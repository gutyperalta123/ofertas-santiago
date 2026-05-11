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


def precio_formulario_a_float(precio_raw):
    precio_raw = (precio_raw or "").strip()
    if not precio_raw:
        return 0

    precio_limpio = precio_raw.replace(".", "").replace(",", ".")

    try:
        precio = float(precio_limpio)
        if precio < 0:
            raise ValueError
        return precio
    except ValueError:
        return None


def categoria_existe(slug):
    conn = get_db()
    c = conn.cursor()
    categoria = c.execute("""
        SELECT slug
        FROM categories
        WHERE slug = ?
          AND active = 1
    """, (slug,)).fetchone()
    conn.close()
    return categoria is not None


def obtener_categorias_activas():
    conn = get_db()
    c = conn.cursor()
    categorias = c.execute("""
        SELECT *
        FROM categories
        WHERE active = 1
        ORDER BY nombre COLLATE NOCASE ASC
    """).fetchall()
    conn.close()
    return categorias


def normalizar_tipo_publicacion(tipo):
    tipo = (tipo or "venta").strip().lower()
    if categoria_existe(tipo):
        return tipo
    return "otros"


@product_routes.route("/api/categories", methods=["GET"])
def api_categories():
    conn = get_db()
    c = conn.cursor()

    rows = c.execute("""
        SELECT nombre, slug
        FROM categories
        WHERE active = 1
        ORDER BY nombre COLLATE NOCASE ASC
    """).fetchall()

    conn.close()

    return jsonify([
        {"nombre": row["nombre"], "slug": row["slug"]}
        for row in rows
    ])


@product_routes.route("/api/products", methods=["GET"])
def list_products():
    conn = get_db()
    c = conn.cursor()

    rows = c.execute("""
        SELECT
            p.id,
            p.tipo_publicacion,
            p.rubro,
            p.titulo,
            p.descripcion,
            p.precio,
            p.imagen,
            p.tienda_nombre,
            p.ciudad,
            p.whatsapp_link,
            p.instagram_link,
            p.facebook_link,
            COALESCE(c.nombre, p.tipo_publicacion) AS categoria_nombre
        FROM products p
        LEFT JOIN categories c ON c.slug = p.tipo_publicacion
        WHERE p.active = 1
          AND p.sold = 0
        ORDER BY
            CASE WHEN p.precio IS NULL OR p.precio = 0 THEN 1 ELSE 0 END ASC,
            p.precio ASC,
            p.id DESC
    """).fetchall()

    conn.close()

    productos = []

    for row in rows:
        productos.append({
            "id": row["id"],
            "tipo_publicacion": row["tipo_publicacion"] or "venta",
            "categoria_nombre": row["categoria_nombre"] or "Venta",
            "rubro": row["rubro"] or "",
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
          AND active = 1
          AND sold = 0
        ORDER BY ciudad COLLATE NOCASE ASC
    """).fetchall()

    conn.close()

    return jsonify([row["ciudad"] for row in rows])


@product_routes.route("/seller/dashboard", methods=["GET", "POST"])
def seller_dashboard():
    if not usuario_logueado():
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        tipo_publicacion = normalizar_tipo_publicacion(request.form.get("tipo_publicacion", "venta"))
        rubro = request.form.get("rubro", "").strip()
        tienda_nombre = request.form.get("tienda_nombre", "").strip()
        titulo = request.form.get("titulo", "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        precio_raw = request.form.get("precio", "").strip()
        ciudad = request.form.get("ciudad", "").strip()
        whatsapp_numero = request.form.get("whatsapp_link", "").strip()
        instagram_link = request.form.get("instagram_link", "").strip()
        facebook_link = request.form.get("facebook_link", "").strip()
        imagen_file = request.files.get("imagen")

        if not tienda_nombre:
            flash("Ingresá el nombre de tu tienda, empresa o nombre público.", "danger")
            return redirect(url_for("products.seller_dashboard"))

        if not titulo or not ciudad:
            flash("Completá título y ciudad.", "danger")
            return redirect(url_for("products.seller_dashboard"))

        precio = precio_formulario_a_float(precio_raw)

        if precio is None:
            flash("El precio debe ser válido. Si no querés poner precio, dejalo vacío.", "danger")
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
                user_id, tipo_publicacion, rubro, titulo, descripcion, precio,
                imagen, tienda_nombre, ciudad, whatsapp_link, instagram_link,
                facebook_link, active, sold
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"], tipo_publicacion, rubro, titulo, descripcion,
            precio, imagen, tienda_nombre, ciudad, whatsapp_link,
            instagram_link, facebook_link, 1, 0
        ))

        conn.commit()
        conn.close()

        flash("Publicación cargada correctamente.", "success")
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

    categorias = obtener_categorias_activas()

    return render_template(
        "seller_dashboard.html",
        publicaciones=publicaciones,
        user=user,
        categorias=categorias
    )


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
        flash("Publicación no encontrada.", "danger")
        return redirect(url_for("products.seller_dashboard"))

    if not puede_tocar_producto(producto, session["user_id"], session["role"]):
        conn.close()
        flash("No podés editar esta publicación.", "danger")
        return redirect(url_for("products.seller_dashboard"))

    if request.method == "POST":
        tipo_publicacion = normalizar_tipo_publicacion(request.form.get("tipo_publicacion", "venta"))
        rubro = request.form.get("rubro", "").strip()
        tienda_nombre = request.form.get("tienda_nombre", "").strip()
        titulo = request.form.get("titulo", "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        precio_raw = request.form.get("precio", "").strip()
        ciudad = request.form.get("ciudad", "").strip()
        whatsapp_numero = request.form.get("whatsapp_link", "").strip()
        instagram_link = request.form.get("instagram_link", "").strip()
        facebook_link = request.form.get("facebook_link", "").strip()
        imagen_actual = request.form.get("imagen_actual", "").strip()
        imagen_file = request.files.get("imagen")

        if not tienda_nombre:
            conn.close()
            flash("Ingresá el nombre de tu tienda, empresa o nombre público.", "danger")
            return redirect(url_for("products.edit_product", product_id=product_id))

        if not titulo or not ciudad:
            conn.close()
            flash("Completá título y ciudad.", "danger")
            return redirect(url_for("products.edit_product", product_id=product_id))

        precio = precio_formulario_a_float(precio_raw)

        if precio is None:
            conn.close()
            flash("El precio debe ser válido. Si no querés poner precio, dejalo vacío.", "danger")
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
                tipo_publicacion = ?,
                rubro = ?,
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
            tipo_publicacion,
            rubro,
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

        conn.commit()
        conn.close()

        flash("Publicación editada correctamente.", "success")

        if session["role"] == "admin" and producto["user_id"] != session["user_id"]:
            return redirect(url_for("admin.admin_user_detail", user_id=producto["user_id"]))

        return redirect(url_for("products.seller_dashboard"))

    producto_dict = dict(producto)
    producto_dict["whatsapp_numero"] = whatsapp_link_a_numero(producto["whatsapp_link"] or "")

    conn.close()

    categorias = obtener_categorias_activas()

    return render_template(
        "edit_product.html",
        producto=producto_dict,
        categorias=categorias
    )


@product_routes.route("/seller/product/<int:product_id>/delete", methods=["POST"])
def delete_product(product_id):
    if not usuario_logueado():
        return redirect(url_for("auth.login"))

    conn = get_db()
    c = conn.cursor()

    producto = c.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()

    if not producto:
        conn.close()
        flash("Publicación no encontrada.", "danger")
        return redirect(url_for("products.seller_dashboard"))

    if not puede_tocar_producto(producto, session["user_id"], session["role"]):
        conn.close()
        flash("No podés eliminar esta publicación.", "danger")
        return redirect(url_for("products.seller_dashboard"))

    c.execute("DELETE FROM products WHERE id = ?", (product_id,))

    conn.commit()
    conn.close()

    flash("Publicación eliminada correctamente.", "success")

    if session["role"] == "admin" and producto["user_id"] != session["user_id"]:
        return redirect(url_for("admin.admin_user_detail", user_id=producto["user_id"]))

    return redirect(url_for("products.seller_dashboard"))


@product_routes.route("/seller/product/<int:product_id>/sold", methods=["POST"])
def mark_as_sold(product_id):
    if not usuario_logueado():
        return redirect(url_for("auth.login"))

    conn = get_db()
    c = conn.cursor()

    producto = c.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()

    if not producto:
        conn.close()
        flash("Publicación no encontrada.", "danger")
        return redirect(url_for("products.seller_dashboard"))

    if not puede_tocar_producto(producto, session["user_id"], session["role"]):
        conn.close()
        flash("No podés finalizar esta publicación.", "danger")
        return redirect(url_for("products.seller_dashboard"))

    c.execute("UPDATE products SET sold = 1 WHERE id = ?", (product_id,))

    conn.commit()
    conn.close()

    flash("Publicación finalizada.", "success")

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

    conn = get_db()
    c = conn.cursor()

    afectados = 0

    for pid in product_ids:
        producto = c.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()

        if not producto:
            continue

        if not puede_tocar_producto(producto, session["user_id"], session["role"]):
            continue

        if bulk_action == "delete":
            c.execute("DELETE FROM products WHERE id = ?", (pid,))
            afectados += 1

        elif bulk_action == "sold":
            c.execute("UPDATE products SET sold = 1 WHERE id = ?", (pid,))
            afectados += 1

    conn.commit()
    conn.close()

    flash(f"Se modificaron {afectados} publicaciones.", "success")

    if return_to == "admin_detail" and owner_user_id:
        return redirect(url_for("admin.admin_user_detail", user_id=owner_user_id))

    return redirect(url_for("products.seller_dashboard"))