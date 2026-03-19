# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 10:55:42 2026
@author: nakan
"""

import sqlite3

TECNICOS = [
    "Juan Perez",
    "Luis Garcia",
    "Maria Lopez",
    "Carlos Ramirez"
]

def connect():
    return sqlite3.connect("inventario.db")

def create_tables():

    conn = connect()
    cursor = conn.cursor()

    # 👨‍🔧 TABLA PERSONAL
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS personal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        puesto TEXT,
        qr TEXT
    )
    """)

    # 📦 TABLA PRODUCTOS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        numero_parte TEXT UNIQUE,
        stock INTEGER DEFAULT 0,
        fecha_ingreso TEXT,
        qr TEXT
    )
    """)

    # 🔄 TABLA MOVIMIENTOS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movimientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        tipo TEXT,
        tecnico TEXT,
        producto_id INTEGER,
        cantidad INTEGER,
        matricula TEXT,
        descripcion TEXT
    )
    """)

    # 🔧 ACTUALIZACIÓN AUTOMÁTICA DE COLUMNAS
    # (para bases de datos ya existentes)

    # productos → fecha_ingreso
    try:
        cursor.execute("ALTER TABLE productos ADD COLUMN fecha_ingreso TEXT")
    except:
        pass

    # movimientos → matricula
    try:
        cursor.execute("ALTER TABLE movimientos ADD COLUMN matricula TEXT")
    except:
        pass

    # movimientos → descripcion
    try:
        cursor.execute("ALTER TABLE movimientos ADD COLUMN descripcion TEXT")
    except:
        pass

    conn.commit()
    conn.close()