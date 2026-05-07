# =========================================================
# BASE DE DATOS SQLITE - OFERTAS SANTIAGO
# =========================================================

import sqlite3

DB_NAME = "database.db"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def column_exists(cursor, table_name, column_name):
    rows = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    for row in rows:
        if row[1] == column_name:
            return True
    return False


def add_column_if_missing(cursor, table_name, column_sql):
    column_name = column_sql.split()[0]
    if not column_exists(cursor, table_name, column_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")


def init_db():
    conn = get_db()
    c = conn.cursor()

    # =========================
    # USERS
    # =========================
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            telefono TEXT UNIQUE,
            password TEXT,
            tienda_nombre TEXT,
            ciudad TEXT,
            role TEXT DEFAULT 'seller',
            blocked INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    add_column_if_missing(c, "users", "email TEXT UNIQUE")
    add_column_if_missing(c, "users", "telefono TEXT UNIQUE")
    add_column_if_missing(c, "users", "password TEXT")
    add_column_if_missing(c, "users", "tienda_nombre TEXT")
    add_column_if_missing(c, "users", "ciudad TEXT")
    add_column_if_missing(c, "users", "role TEXT DEFAULT 'seller'")
    add_column_if_missing(c, "users", "blocked INTEGER DEFAULT 0")

    # =========================
    # PRODUCTS / PUBLICACIONES
    # =========================
    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            tipo_publicacion TEXT DEFAULT 'venta',
            rubro TEXT,
            titulo TEXT NOT NULL,
            descripcion TEXT,
            precio REAL NOT NULL DEFAULT 0,
            imagen TEXT,
            tienda_nombre TEXT NOT NULL,
            ciudad TEXT NOT NULL,
            whatsapp_link TEXT,
            instagram_link TEXT,
            facebook_link TEXT,
            active INTEGER DEFAULT 1,
            sold INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    add_column_if_missing(c, "products", "user_id INTEGER")
    add_column_if_missing(c, "products", "tipo_publicacion TEXT DEFAULT 'venta'")
    add_column_if_missing(c, "products", "rubro TEXT")
    add_column_if_missing(c, "products", "descripcion TEXT")
    add_column_if_missing(c, "products", "imagen TEXT")
    add_column_if_missing(c, "products", "tienda_nombre TEXT")
    add_column_if_missing(c, "products", "ciudad TEXT")
    add_column_if_missing(c, "products", "whatsapp_link TEXT")
    add_column_if_missing(c, "products", "instagram_link TEXT")
    add_column_if_missing(c, "products", "facebook_link TEXT")
    add_column_if_missing(c, "products", "active INTEGER DEFAULT 1")
    add_column_if_missing(c, "products", "sold INTEGER DEFAULT 0")

    conn.commit()

    # =========================
    # ADMIN FIJO
    # =========================
    admin = c.execute(
        "SELECT id FROM users WHERE email = ?",
        ("gutyperalta123@gmail.com",)
    ).fetchone()

    if not admin:
        c.execute("""
            INSERT INTO users (
                email, telefono, password, tienda_nombre, ciudad, role, blocked
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "gutyperalta123@gmail.com",
            "3850000000",
            "Sukoisu30mk2",
            "OFERTAS SANTIAGO",
            "Santiago del Estero",
            "admin",
            0
        ))
        conn.commit()

    # =========================
    # PRODUCTOS INICIALES
    # =========================
    total = c.execute("SELECT COUNT(*) AS total FROM products").fetchone()["total"]

    if total == 0:
        admin_user = c.execute(
            "SELECT id, tienda_nombre FROM users WHERE email = ?",
            ("gutyperalta123@gmail.com",)
        ).fetchone()

        productos_iniciales = [
            (
                admin_user["id"],
                "venta",
                "Motos",
                "Moto 110cc usada",
                "Moto económica en excelente estado.",
                1850000,
                "https://images.unsplash.com/photo-1558981806-ec527fa84c39?auto=format&fit=crop&w=900&q=80",
                admin_user["tienda_nombre"],
                "Santiago Capital",
                "https://wa.me/5493854000000",
                "https://instagram.com/ofertassantiago",
                "https://facebook.com/ofertassantiago",
                1,
                0
            ),
            (
                admin_user["id"],
                "venta",
                "Electrodomésticos",
                "Heladera familiar",
                "Gran capacidad y bajo consumo.",
                980000,
                "https://images.unsplash.com/photo-1584568694244-14fbdf83bd30?auto=format&fit=crop&w=900&q=80",
                admin_user["tienda_nombre"],
                "La Banda",
                "https://wa.me/5493854000000",
                "https://instagram.com/ofertassantiago",
                "https://facebook.com/ofertassantiago",
                1,
                0
            ),
            (
                admin_user["id"],
                "venta",
                "Tecnología",
                "Notebook 15 pulgadas",
                "Ideal para estudio y trabajo.",
                1250000,
                "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=900&q=80",
                admin_user["tienda_nombre"],
                "Termas de Río Hondo",
                "https://wa.me/5493854000000",
                "https://instagram.com/ofertassantiago",
                "https://facebook.com/ofertassantiago",
                1,
                0
            )
        ]

        c.executemany("""
            INSERT INTO products (
                user_id,
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
                active,
                sold
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, productos_iniciales)

        conn.commit()

    conn.close()