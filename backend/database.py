import sqlite3

DB_NAME = "database.db"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def column_exists(cursor, table_name, column_name):
    rows = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row[1] == column_name for row in rows)


def add_column_if_missing(cursor, table_name, column_sql):
    column_name = column_sql.split()[0]
    if not column_exists(cursor, table_name, column_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")


def init_db():
    conn = get_db()
    c = conn.cursor()

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

    c.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL UNIQUE,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

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

    add_column_if_missing(c, "products", "tipo_publicacion TEXT DEFAULT 'venta'")
    add_column_if_missing(c, "products", "rubro TEXT")
    add_column_if_missing(c, "products", "active INTEGER DEFAULT 1")
    add_column_if_missing(c, "products", "sold INTEGER DEFAULT 0")

    categorias_iniciales = [
        ("Venta", "venta"),
        ("Servicio", "servicio"),
        ("Salud", "salud"),
        ("Educación", "educacion"),
        ("Construcción", "construccion"),
        ("Refrigeración", "refrigeracion"),
        ("Plomería", "plomeria"),
        ("Electricidad", "electricidad"),
        ("Reparación de celulares", "reparacion-celulares"),
        ("Reparación de electrodomésticos", "reparacion-electrodomesticos"),
        ("Otros", "otros"),
    ]

    for nombre, slug in categorias_iniciales:
        existe = c.execute("SELECT id FROM categories WHERE slug = ?", (slug,)).fetchone()
        if not existe:
            c.execute("""
                INSERT INTO categories (nombre, slug, active)
                VALUES (?, ?, 1)
            """, (nombre, slug))

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
    conn.close()