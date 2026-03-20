# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify, render_template, send_file, session, redirect, url_for
import sqlite3
import qrcode
import os
import pandas as pd
from db import create_tables
from datetime import datetime
import pytz
import re

app = Flask(__name__)
app.secret_key = "edae_secret_123"

# 🔥 RUTA PERSISTENTE EN RENDER
DB_PATH = "/data/inventario.db"

create_tables()

TECNICOS = [
    "Habacuc de la Vara Ramirez",
    "Angel Perez",
    "Carlos Zesati",
    "Ruben Castañon",
    "Salvador Hernandez",
    "Adir Martinez",
    "Alexia Anda",
    "Minerva Hernandez",
    "Ray"
]

USUARIOS = {
    "admin": "1234",
    "ELVER": "ADIR"
}

def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def protegido():
    return "user" in session


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("user")
        password = request.form.get("password")

        if user in USUARIOS and USUARIOS[user] == password:
            session["user"] = user
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Credenciales incorrectas")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
def index():
    if not protegido():
        return redirect("/login")

    from datetime import date

    return render_template(
        "index.html",
        tecnicos=TECNICOS,
        fecha_hoy=date.today().strftime("%Y-%m-%d")
    )


@app.route("/qr/<codigo>")
def ver_qr(codigo):

    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT nombre, numero_parte, fecha_ingreso, fabricante FROM productos WHERE qr = ?",
            (codigo,)
        )
        producto = cursor.fetchone()

    if producto:
        nombre = producto["nombre"]
        numero = producto["numero_parte"]
        fecha_ingreso = producto["fecha_ingreso"]
        fabricante = producto["fabricante"]
    else:
        nombre, numero, fecha_ingreso, fabricante = "Desconocido", codigo, "Desconocida", "Desconocido"

    return f"""
    <html>
    <body style="text-align:center;font-family:Arial">
        <h2>{nombre}</h2>
        <h3>NP: {numero}</h3>
        <h3>Fabricante: {fabricante}</h3>
        <h3>Fecha: {fecha_ingreso}</h3>
        <img src='/static/qrs/{codigo}.png' width='200'>
        <br><br>
        <button onclick="window.print()">Imprimir</button>
    </body>
    </html>
    """


@app.route("/crear_producto", methods=["POST"])
def crear_producto():

    if not protegido():
        return jsonify({"error": "No autorizado"})

    data = request.json

    nombre = data["nombre"]
    numero_parte = data["numero_parte"].strip()
    stock = int(data["stock"])
    fecha_ingreso = data.get("fecha_ingreso", "")
    fabricante = data.get("fabricante", "")

    codigo = re.sub(r'[^A-Za-z0-9_-]', '_', numero_parte)

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM productos WHERE numero_parte = ?",
            (numero_parte,)
        )

        if cursor.fetchone():
            return jsonify({"error": "El producto ya existe"})

        cursor.execute("""
        INSERT INTO productos (nombre, numero_parte, stock, fecha_ingreso, qr, fabricante)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (nombre, numero_parte, stock, fecha_ingreso, codigo, fabricante))

        os.makedirs("static/qrs", exist_ok=True)

        img = qrcode.make(codigo)
        img.save(f"static/qrs/{codigo}.png")

        conn.commit()

    return jsonify({"status": "ok"})


@app.route("/movimiento", methods=["POST"])
def movimiento():

    if not protegido():
        return jsonify({"error": "No autorizado"})

    try:
        data = request.json

        tipo = data.get("tipo")
        producto_qr = data.get("producto_qr")
        cantidad = int(data.get("cantidad"))
        tecnico = data.get("tecnico")
        matricula = data.get("matricula", "")
        descripcion = data.get("descripcion", "")

        zona = pytz.timezone("America/Mexico_City")
        fecha = datetime.now(zona).strftime("%Y-%m-%d %H:%M:%S")

        with connect() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id, stock FROM productos WHERE qr = ?",
                (producto_qr,)
            )

            producto = cursor.fetchone()

            if not producto:
                return jsonify({"error": "Producto no encontrado"})

            producto_id = producto["id"]
            stock = producto["stock"]

            if tipo == "SALIDA" and stock < cantidad:
                return jsonify({"error": "Stock insuficiente"})

            cursor.execute("""
            INSERT INTO movimientos
            (tipo, tecnico, producto_id, cantidad, fecha, matricula, descripcion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (tipo, tecnico, producto_id, cantidad, fecha, matricula, descripcion))

            if tipo == "SALIDA":
                cursor.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (cantidad, producto_id))
            elif tipo == "ENTRADA":
                cursor.execute("UPDATE productos SET stock = stock + ? WHERE id = ?", (cantidad, producto_id))
            elif tipo == "AJUSTE":
                cursor.execute("UPDATE productos SET stock = ? WHERE id = ?", (cantidad, producto_id))

            conn.commit()

        return jsonify({"status": "ok"})

    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/ver_datos")
def ver_datos():

    if not protegido():
        return redirect("/login")

    buscar = request.args.get("buscar")

    with connect() as conn:
        cursor = conn.cursor()

        if buscar:
            cursor.execute("SELECT * FROM productos WHERE numero_parte LIKE ?", (f"%{buscar}%",))
        else:
            cursor.execute("SELECT * FROM productos")

        productos = cursor.fetchall()

        cursor.execute("""
        SELECT m.id, m.tipo, m.tecnico, p.nombre,
        m.cantidad, m.fecha, m.matricula, m.descripcion
        FROM movimientos m
        JOIN productos p ON m.producto_id = p.id
        """)

        movimientos = cursor.fetchall()

    return render_template("ver_datos.html", productos=productos, movimientos=movimientos, tecnicos=TECNICOS)


@app.route("/reporte_excel")
def reporte_excel():

    if not protegido():
        return redirect("/login")

    with connect() as conn:
        df = pd.read_sql_query("""
        SELECT m.tipo, m.tecnico, p.nombre, m.cantidad, m.fecha, m.matricula, m.descripcion
        FROM movimientos m
        JOIN productos p ON m.producto_id = p.id
        """, conn)

    archivo = "/data/reporte.xlsx"
    df.to_excel(archivo, index=False)

    return send_file(archivo, as_attachment=True)


# 🔥 RUN PARA RENDER
if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
