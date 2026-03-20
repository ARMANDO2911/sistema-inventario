# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify, render_template, send_file, session, redirect, url_for
import sqlite3
import qrcode
import os
import pandas as pd
from db import create_tables
from datetime import datetime
import pytz

app = Flask(__name__)
app.secret_key = "edae_secret_123"

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
    return sqlite3.connect("inventario.db", timeout=30)

def protegido():
    return "user" in session

# LOGIN
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

# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# INDEX
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

# QR
@app.route("/qr/<codigo>")
def ver_qr(codigo):

    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT nombre, numero_parte, fecha_ingreso FROM productos WHERE qr = ?",
            (codigo,)
        )
        producto = cursor.fetchone()

    if producto:
        nombre, numero, fecha_ingreso = producto
        if not fecha_ingreso:
            fecha_ingreso = "Desconocida"
    else:
        nombre, numero, fecha_ingreso = "Desconocido", codigo, "Desconocida"

    return f"""
    <html>
    <body style="text-align:center;font-family:Arial">

    <div style="border:2px solid black; display:inline-block; padding:20px;">
        <h2>EDAE</h2>
        <h3>{nombre}</h3>
        <h3>NP: {numero}</h3>
        <h3>Fecha de ingreso: {fecha_ingreso}</h3>

        <img src='/static/qrs/{codigo}.png' width='200'>

        <h3>{codigo}</h3>
    </div>

    <br><br>

    <button onclick="window.print()">🖨️ Imprimir</button>

    </body>
    </html>
    """

# CREAR PRODUCTO
@app.route("/crear_producto", methods=["POST"])
def crear_producto():

    if not protegido():
        return jsonify({"error": "No autorizado"})

    data = request.json

    nombre = data["nombre"]
    numero_parte = data["numero_parte"]
    stock = int(data["stock"])
    fecha_ingreso = data.get("fecha_ingreso", "")

    codigo = numero_parte

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM productos WHERE numero_parte = ?",
            (numero_parte,)
        )

        if cursor.fetchone():
            return jsonify({"error": "El producto ya existe"})

        cursor.execute("""
        INSERT INTO productos (nombre, numero_parte, stock, fecha_ingreso, qr)
        VALUES (?, ?, ?, ?, ?)
        """, (nombre, numero_parte, stock, fecha_ingreso, codigo))

        os.makedirs("static/qrs", exist_ok=True)

        img = qrcode.make(codigo)
        img.save(f"static/qrs/{codigo}.png")

        conn.commit()

    return jsonify({"status": "ok"})

# MOVIMIENTO
@app.route("/movimiento", methods=["POST"])
def movimiento():

    if not protegido():
        return jsonify({"error": "No autorizado"})

    try:
        data = request.json

        tipo = data.get("tipo")
        producto_qr = data.get("producto_qr")
        cantidad = int(data.get("cantidad", 0))
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

            producto_id, stock = producto

            if tipo == "SALIDA" and stock < cantidad:
                return jsonify({"error": "Stock insuficiente"})

            cursor.execute("""
            INSERT INTO movimientos
            (tipo, tecnico, producto_id, cantidad, fecha, matricula, descripcion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                tipo,
                tecnico,
                producto_id,
                cantidad,
                fecha,
                matricula,
                descripcion
            ))

            if tipo == "SALIDA":
                cursor.execute(
                    "UPDATE productos SET stock = stock - ? WHERE id = ?",
                    (cantidad, producto_id)
                )

            elif tipo == "ENTRADA":
                cursor.execute(
                    "UPDATE productos SET stock = stock + ? WHERE id = ?",
                    (cantidad, producto_id)
                )

            conn.commit()

        return jsonify({"status": "ok"})

    except Exception as e:
        return jsonify({"error": str(e)})

# VER DATOS
@app.route("/ver_datos")
def ver_datos():

    if not protegido():
        return redirect("/login")

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM productos")
        productos = cursor.fetchall()

        cursor.execute("""
        SELECT
        m.id,
        m.tipo,
        m.tecnico,
        p.nombre,
        m.cantidad,
        m.fecha,
        m.matricula,
        m.descripcion
        FROM movimientos m
        JOIN productos p ON m.producto_id = p.id
        """)

        movimientos = cursor.fetchall()

    return render_template(
        "ver_datos.html",
        productos=productos,
        movimientos=movimientos,
        tecnicos=TECNICOS
    )

# REPORTE EXCEL
@app.route("/reporte_excel")
def reporte_excel():

    if not protegido():
        return redirect("/login")

    with connect() as conn:
        query = """
        SELECT
        m.id,
        m.tipo,
        m.tecnico,
        p.nombre,
        m.cantidad,
        m.fecha,
        m.matricula,
        m.descripcion
        FROM movimientos m
        JOIN productos p ON m.producto_id = p.id
        """

        df = pd.read_sql_query(query, conn)

    archivo = "reporte.xlsx"
    df.to_excel(archivo, index=False)

    return send_file(archivo, as_attachment=True)

# RUN PARA RENDER
if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
