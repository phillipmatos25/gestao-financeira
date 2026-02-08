from flask import Flask, render_template, request, redirect, url_for, session
from collections import defaultdict
from datetime import datetime, date
import sqlite3
import os
from dateutil.relativedelta import relativedelta
from werkzeug.security import generate_password_hash, check_password_hash

# ==============================
# APP
# ==============================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "chave-secreta")

# ==============================
# DATABASE CONFIG
# ==============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    print(">>> INIT_DB EXECUTANDO <<<")
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            descricao TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cartoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            bandeira TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            data_pagamento TEXT,
            descricao TEXT,
            categoria TEXT,
            cartao INTEGER,
            valor REAL NOT NULL,
            tipo TEXT NOT NULL,
            parcelas INTEGER,
            parcela_numero INTEGER,
            paga INTEGER DEFAULT 0,
            usuario_id INTEGER,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    """)

    conn.commit()
    conn.close()


# EXECUTA A CRIAÇÃO DO BANCO AO SUBIR O APP
init_db()

# ==============================
# GERAR MESES
# ==============================
def gerar_meses(desde_ano=2025):
    hoje = date.today()
    meses = []
    ano = desde_ano
    mes = 1

    while (ano < hoje.year) or (ano == hoje.year and mes <= hoje.month):
        meses.append(f"{ano}-{mes:02d}")
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1

    return meses


# ==============================
# FILTRO MOEDA
# ==============================
@app.template_filter('format_currency')
def format_currency(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (TypeError, ValueError):
        return "R$ 0,00"


# ==============================
# ROTAS
# ==============================
@app.route("/")
def home():
    return redirect(url_for("login"))


# ==============================
# LOGIN
# ==============================
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['senha'], password):
            session['usuario'] = username
            return redirect(url_for('index'))
        else:
            error = "Usuário ou senha inválidos."

    return render_template("login.html", error=error)


@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))


# ==============================
# INDEX
# ==============================
@app.route('/index', methods=['GET', 'POST'])
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    filtro_mes = request.args.get('mes')
    filtro_pago = request.args.get('pago')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM usuarios WHERE username = ?", (session['usuario'],))
    usuario_id = cursor.fetchone()['id']

    if request.method == 'POST':
        if 'excluir_movimentacao' in request.form:
            cursor.execute(
                'DELETE FROM movimentacoes WHERE id = ? AND usuario_id = ?',
                (request.form['movimentacao_id'], usuario_id)
            )
            conn.commit()
            return redirect(url_for('index', mes=filtro_mes, pago=filtro_pago))

    query = "SELECT * FROM movimentacoes WHERE usuario_id = ?"
    params = [usuario_id]

    if filtro_mes:
        query += " AND strftime('%Y-%m', data_pagamento) = ?"
        params.append(filtro_mes)

    if filtro_pago == 'sim':
        query += " AND paga = 1"
    elif filtro_pago == 'nao':
        query += " AND paga = 0"

    query += " ORDER BY data_pagamento"
    cursor.execute(query, params)
    movimentacoes = cursor.fetchall()

    cursor.execute("SELECT id, nome FROM categorias ORDER BY nome ASC")
    categorias = cursor.fetchall()

    cursor.execute("SELECT id, nome, bandeira FROM cartoes ORDER BY bandeira ASC")
    cartoes = cursor.fetchall()

    conn.close()

    return render_template(
        'index.html',
        movimentacoes=movimentacoes,
        categorias=categorias,
        cartoes=cartoes,
        meses_disponiveis=gerar_meses(2025),
        usuario=session['usuario']
    )


# ==============================
# RUN
# ==============================
if __name__ == '__main__':
    app.run()