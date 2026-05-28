import os
import sqlite3
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# Carga backend/.env en local.
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "database.db")


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


def crear_o_actualizar_admin(cursor):
    """
    Crea o actualiza el usuario administrador usando variables de entorno.
    Así no queda email, teléfono ni contraseña escritos dentro de GitHub.
    """
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    admin_phone = os.getenv("ADMIN_PHONE", "").strip()
    admin_password = os.getenv("ADMIN_PASSWORD", "").strip()

    # Si no configuraste el .env, no crea admin automático.
    # Esto evita que GitHub tenga credenciales fijas.
    if not admin_email or not admin_phone or not admin_password:
        return

    password_hash = generate_password_hash(admin_password)

    admin = cursor.execute(
        "SELECT id FROM users WHERE email = ?",
        (admin_email,)
    ).fetchone()

    if admin:
        # Si el admin ya existe, actualiza teléfono, password hasheado y rol.
        cursor.execute("""
            UPDATE users
            SET telefono = ?,
                password = ?,
                tienda_nombre = ?,
                ciudad = ?,
                role = ?,
                blocked = ?
            WHERE email = ?
        """, (
            admin_phone,
            password_hash,
            "OFERTAS SANTIAGO",
            "Santiago del Estero",
            "admin",
            0,
            admin_email
        ))
    else:
        cursor.execute("""
            INSERT INTO users (
                email, telefono, password, tienda_nombre, ciudad, role, blocked
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            admin_email,
            admin_phone,
            password_hash,
            "OFERTAS SANTIAGO",
            "Santiago del Estero",
            "admin",
            0
        ))


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
        existe = c.execute(
            "SELECT id FROM categories WHERE slug = ?",
            (slug,)
        ).fetchone()

        if not existe:
            c.execute("""
                INSERT INTO categories (nombre, slug, active)
                VALUES (?, ?, 1)
            """, (nombre, slug))

    crear_o_actualizar_admin(c)

    conn.commit()
    conn.close()
