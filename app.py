from flask import Flask, render_template, request, redirect, url_for, session
from collections import defaultdict
from datetime import datetime, date
import psycopg2
import psycopg2.extras
import os
from dateutil.relativedelta import relativedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "chave-secreta"

# ==============================
# JINJA FILTERS
# ==============================
@app.template_filter('format_currency')
def format_currency(value):
    try:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"

# ==============================
# DATABASE
# ==============================
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor
    )


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            descricao TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cartoes (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            bandeira TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimentacoes (
            id SERIAL PRIMARY KEY,
            data DATE NOT NULL,
            data_pagamento DATE,
            descricao TEXT,
            categoria TEXT,
            cartao INTEGER,
            valor NUMERIC(10,2) NOT NULL,
            tipo TEXT NOT NULL,
            parcelas INTEGER,
            parcela_numero INTEGER,
            paga BOOLEAN DEFAULT FALSE,
            usuario_id INTEGER REFERENCES usuarios(id)
        )
    """)

    # cria usuário admin padrão se não existir
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()["count"] == 0:
        cursor.execute(
            "INSERT INTO usuarios (username, senha) VALUES (%s, %s)",
            ("phillip_matos", generate_password_hash("741852963!@#"))
        )
        print(">>> Usuário admin criado (phillip_matos / 741852963!@#)")

    conn.commit()
    cursor.close()
    conn.close()


# ⚠️ cria o banco ao subir o app
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
        cursor.execute(
            "SELECT * FROM usuarios WHERE username = %s",
            (username,)
        )
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
# HOME
# ==============================
@app.route('/')
def home():
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

    cursor.execute(
        "SELECT id FROM usuarios WHERE username = %s",
        (session['usuario'],)
    )
    usuario = cursor.fetchone()

    # primeiro acesso: cria usuário automaticamente
    if not usuario:
        cursor.execute(
            "INSERT INTO usuarios (username, senha) VALUES (%s, %s)",
            (session['usuario'], generate_password_hash("123"))
        )
        conn.commit()
        cursor.execute(
            "SELECT id FROM usuarios WHERE username = %s",
            (session['usuario'],)
        )
        usuario = cursor.fetchone()

    usuario_id = usuario['id']

    query = "SELECT * FROM movimentacoes WHERE usuario_id = %s"
    params = [usuario_id]

    if filtro_mes:
        query += " AND TO_CHAR(data_pagamento, 'YYYY-MM') = %s"
        params.append(filtro_mes)

    if filtro_pago == 'sim':
        query += " AND paga = TRUE"
    elif filtro_pago == 'nao':
        query += " AND paga = FALSE"

    query += " ORDER BY data_pagamento"
    cursor.execute(query, params)
    movimentacoes = cursor.fetchall()

    cursor.execute("SELECT id, nome FROM categorias ORDER BY nome ASC")
    categorias = cursor.fetchall()

    cursor.execute("SELECT id, nome, bandeira FROM cartoes ORDER BY bandeira ASC")
    cartoes = cursor.fetchall()
    cartoes_dict = {c['id']: c for c in cartoes}

    movimentacoes_formatadas = [{
        'id': m['id'],
        'data': m['data'],
        'data_pagamento': m['data_pagamento'],
        'descricao': m['descricao'],
        'categoria': m['categoria'],
        'cartao': cartoes_dict.get(m['cartao']),
        'valor': float(m['valor']),
        'tipo': m['tipo'],
        'parcelas': m['parcelas'],
        'parcela_numero': m['parcela_numero'],
        'paga': m['paga']
    } for m in movimentacoes]

    total_receitas = sum(m['valor'] for m in movimentacoes_formatadas if m['tipo'] == 'receita')
    total_despesas = sum(m['valor'] for m in movimentacoes_formatadas if m['tipo'] == 'despesa')

    conn.close()

    return render_template(
        'index.html',
        movimentacoes=movimentacoes_formatadas,
        categorias=categorias,
        cartoes=cartoes,
        total=total_receitas - total_despesas,
        total_receitas=total_receitas,
        total_despesas=total_despesas,
        filtro_mes=filtro_mes,
        filtro_pago=filtro_pago,
        meses_disponiveis=gerar_meses(2025),
        usuario=session['usuario']
    )


# ==============================
# RUN
# ==============================
if __name__ == '__main__':
    app.run(debug=True)