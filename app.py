from flask import Flask, render_template, request, redirect, url_for, session
from collections import defaultdict
from datetime import datetime, date
import sqlite3
from dateutil.relativedelta import relativedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "chave-secreta"


# ==============================
# DATABASE
# ==============================
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn


# ==============================
# GERAR MESES (2025 ATÉ HOJE)
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
# CADASTROS
# ==============================
@app.route('/cadastros', methods=['GET', 'POST'])
def cadastros():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':

        if 'add_categoria' in request.form:
            cursor.execute(
                'INSERT INTO categorias (nome, descricao) VALUES (?, ?)',
                (request.form['categoria'], request.form['descricao_categoria'])
            )

        elif 'add_cartao' in request.form:
            cursor.execute(
                'INSERT INTO cartoes (nome, bandeira) VALUES (?, ?)',
                (request.form['cartao'], request.form['bandeira_cartao'])
            )

        elif 'excluir_categoria' in request.form:
            cursor.execute(
                'DELETE FROM categorias WHERE id = ?',
                (request.form['categoria_id'],)
            )

        elif 'excluir_cartao' in request.form:
            cursor.execute(
                'DELETE FROM cartoes WHERE id = ?',
                (request.form['cartao_id'],)
            )

        elif 'add_usuario' in request.form:
            try:
                cursor.execute(
                    "INSERT INTO usuarios (username, senha) VALUES (?, ?)",
                    (request.form['novo_username'],
                     generate_password_hash(request.form['novo_senha']))
                )
            except sqlite3.IntegrityError:
                pass

        conn.commit()

    cursor.execute('SELECT * FROM categorias ORDER BY nome ASC')
    categorias = cursor.fetchall()

    cursor.execute('SELECT * FROM cartoes ORDER BY bandeira ASC')
    cartoes = cursor.fetchall()

    cursor.execute('SELECT id, username FROM usuarios')
    usuarios = cursor.fetchall()

    conn.close()

    return render_template(
        'cadastros.html',
        categorias=categorias,
        cartoes=cartoes,
        usuarios=usuarios,
        usuario=session['usuario']
    )


# ==============================
# FILTRO MOEDA (BLINDADO)
# ==============================
@app.template_filter('format_currency')
def format_currency(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (TypeError, ValueError):
        return "R$ 0,00"


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

    cursor.execute("SELECT id FROM usuarios WHERE username = ?", (session['usuario'],))
    usuario_id = cursor.fetchone()['id']

    # ==========================
    # POST
    # ==========================
    if request.method == 'POST':

        if 'excluir_movimentacao' in request.form:
            cursor.execute(
                'DELETE FROM movimentacoes WHERE id = ? AND usuario_id = ?',
                (request.form['movimentacao_id'], usuario_id)
            )
            conn.commit()
            return redirect(url_for('index', mes=filtro_mes, pago=filtro_pago))

        if 'alterar_status_parcela' in request.form:
            cursor.execute(
                'UPDATE movimentacoes SET paga = ? WHERE id = ? AND usuario_id = ?',
                (int(request.form['paga']), request.form['movimentacao_id'], usuario_id)
            )
            conn.commit()
            return redirect(url_for('index', mes=filtro_mes, pago=filtro_pago))

        data_obj = datetime.strptime(request.form['data'], '%Y-%m-%d')
        data_pagamento = request.form.get('data_pagamento')
        data_pagamento_obj = datetime.strptime(data_pagamento, '%Y-%m-%d') if data_pagamento else None

        descricao = request.form['descricao']
        valor_total = float(request.form['valor'])
        tipo = request.form['tipo']
        parcelas = int(request.form.get('parcelas', 1))
        fixa = request.form.get('fixa') == '1'

        cursor.execute("SELECT nome FROM categorias WHERE id = ? ORDER BY nome ASC", (request.form['categoria'],))
        categoria_nome = cursor.fetchone()['nome']

        cartao_id = int(request.form['cartao'])

        if fixa:
            for i in range(12):
                cursor.execute('''
                    INSERT INTO movimentacoes
                    (data, data_pagamento, descricao, categoria, cartao, valor, tipo, parcelas, parcela_numero, paga, usuario_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, 0, ?)
                ''', (
                    (data_obj + relativedelta(months=i)).strftime('%Y-%m-%d'),
                    (data_pagamento_obj + relativedelta(months=i)).strftime('%Y-%m-%d') if data_pagamento_obj else None,
                    descricao, categoria_nome, cartao_id, valor_total, tipo, usuario_id
                ))
        else:
            valor_parcela = round(valor_total / parcelas, 2)
            diferenca = round(valor_total - (valor_parcela * parcelas), 2)

            for i in range(parcelas):
                cursor.execute('''
                    INSERT INTO movimentacoes
                    (data, data_pagamento, descricao, categoria, cartao, valor, tipo, parcelas, parcela_numero, paga, usuario_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                ''', (
                    (data_obj + relativedelta(months=i)).strftime('%Y-%m-%d'),
                    (data_pagamento_obj + relativedelta(months=i)).strftime('%Y-%m-%d') if data_pagamento_obj else None,
                    descricao, categoria_nome, cartao_id,
                    valor_parcela + (diferenca if i == parcelas - 1 else 0),
                    tipo, parcelas, i + 1, usuario_id
                ))

        conn.commit()
        return redirect(url_for('index', mes=filtro_mes, pago=filtro_pago))

    # ==========================
    # GET
    # ==========================
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
    cartoes_dict = {c['id']: {'nome': c['nome'], 'bandeira': c['bandeira']} for c in cartoes}

    movimentacoes_formatadas = [{
        'id': m['id'],
        'data': m['data'],
        'data_pagamento': m['data_pagamento'],
        'descricao': m['descricao'],
        'categoria': m['categoria'],
        'cartao': cartoes_dict.get(m['cartao']),
        'valor': m['valor'],
        'tipo': m['tipo'],
        'parcelas': m['parcelas'],
        'parcela_numero': m['parcela_numero'],
        'paga': bool(m['paga'])
    } for m in movimentacoes]

    total_receitas = sum(m['valor'] for m in movimentacoes_formatadas if m['tipo'] == 'receita')
    total_despesas = sum(m['valor'] for m in movimentacoes_formatadas if m['tipo'] == 'despesa')
    total = total_receitas - total_despesas

    conn.close()

    return render_template(
        'index.html',
        movimentacoes=movimentacoes_formatadas,
        categorias=categorias,
        cartoes=cartoes,
        total=total,
        total_receitas=total_receitas,
        total_despesas=total_despesas,
        filtro_mes=filtro_mes,
        filtro_pago=filtro_pago,
        meses_disponiveis=gerar_meses(2025),
        usuario=session['usuario']
    )


# ==============================
# RESUMO
# ==============================
@app.route('/resumo')
def resumo():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM usuarios WHERE username = ?", (session['usuario'],))
    usuario_id = cursor.fetchone()['id']

    cursor.execute("SELECT * FROM movimentacoes WHERE usuario_id = ?", (usuario_id,))
    movimentacoes = cursor.fetchall()

    categorias_totais = defaultdict(float)
    cartoes_totais = defaultdict(float)

    for m in movimentacoes:
        if m['tipo'] == 'despesa':
            categorias_totais[m['categoria']] += m['valor']
            if m['cartao']:
                cartoes_totais[m['cartao']] += m['valor']

    cursor.execute("SELECT id, nome FROM cartoes ORDER BY bandeira ASC")
    cartoes_map = {c['id']: c['nome'] for c in cursor.fetchall()}

    conn.close()

    return render_template(
        'resumo.html',
        labels_categorias=list(categorias_totais.keys()),
        valores_categorias=list(categorias_totais.values()),
        labels_cartoes=[cartoes_map.get(cid) for cid in cartoes_totais],
        valores_cartoes=list(cartoes_totais.values()),
        usuario=session['usuario']
    )


# ==============================
# RUN
# ==============================
if __name__ == '__main__':
    app.run(debug=True)
