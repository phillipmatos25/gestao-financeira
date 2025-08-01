from flask import Flask, render_template, request, redirect, url_for, session
from collections import defaultdict
from datetime import datetime
import sqlite3
from dateutil.relativedelta import relativedelta  # pip install python-dateutil

app = Flask(__name__)
app.secret_key = "chave-secreta"  # necessário para sessão


def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn


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
        cursor.execute("SELECT * FROM usuarios WHERE username = ? AND senha = ?", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
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
# CADASTROS (Categorias, Cartões e Usuários)
# ==============================
@app.route('/cadastros', methods=['GET', 'POST'])
def cadastros():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        if 'add_categoria' in request.form:
            nome_categoria = request.form['categoria']
            descricao_categoria = request.form['descricao_categoria']
            cursor.execute('INSERT INTO categorias (nome, descricao) VALUES (?, ?)', (nome_categoria, descricao_categoria))
            conn.commit()

        elif 'add_cartao' in request.form:
            cartao = request.form['cartao']
            bandeira_cartao = request.form['bandeira_cartao']
            cursor.execute('INSERT INTO cartoes (nome, bandeira) VALUES (?, ?)', (cartao, bandeira_cartao))
            conn.commit()

        elif 'excluir_categoria' in request.form:
            categoria_id = request.form['categoria_id']
            cursor.execute('DELETE FROM categorias WHERE id = ?', (categoria_id,))
            conn.commit()

        elif 'excluir_cartao' in request.form:
            cartao_id = request.form['cartao_id']
            cursor.execute('DELETE FROM cartoes WHERE id = ?', (cartao_id,))
            conn.commit()

        elif 'add_usuario' in request.form:
            username = request.form['novo_username']
            senha = request.form['novo_senha']
            try:
                cursor.execute("INSERT INTO usuarios (username, senha) VALUES (?, ?)", (username, senha))
                conn.commit()
            except sqlite3.IntegrityError:
                pass  # usuário repetido

    cursor.execute('SELECT * FROM categorias')
    categorias = cursor.fetchall()

    cursor.execute('SELECT * FROM cartoes')
    cartoes = cursor.fetchall()

    cursor.execute('SELECT * FROM usuarios')
    usuarios = cursor.fetchall()

    conn.close()
    return render_template('cadastros.html',
                           categorias=categorias,
                           cartoes=cartoes,
                           usuarios=usuarios,
                           usuario=session['usuario'])


# ==============================
# FILTRO DE MOEDA
# ==============================
@app.template_filter('format_currency')
def format_currency(valor):
    return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


# ==============================
# REDIRECIONAR ROTA RAIZ PARA LOGIN
# ==============================
@app.route('/')
def home():
    return redirect(url_for('login'))


# ==============================
# INDEX (INCLUIR / EDITAR)
# ==============================
@app.route('/index', methods=['GET', 'POST'])
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    filtro_mes = request.args.get('mes')
    filtro_pago = request.args.get('pago')
    edit_id = request.args.get('edit_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    # pegar ID do usuário logado
    cursor.execute("SELECT id FROM usuarios WHERE username = ?", (session['usuario'],))
    usuario_id = cursor.fetchone()['id']

    movimentacao_edit = None

    if request.method == 'POST':
        if 'excluir_movimentacao' in request.form:
            movimentacao_id = request.form['movimentacao_id']
            cursor.execute('DELETE FROM movimentacoes WHERE id = ? AND usuario_id = ?', (movimentacao_id, usuario_id))
            conn.commit()
            return redirect(url_for('index', mes=filtro_mes, pago=filtro_pago))

        if 'alterar_status_parcela' in request.form:
            movimentacao_id = request.form['movimentacao_id']
            paga_novo = int(request.form['paga'])
            cursor.execute('UPDATE movimentacoes SET paga = ? WHERE id = ? AND usuario_id = ?', (paga_novo, movimentacao_id, usuario_id))
            conn.commit()
            return redirect(url_for('index', mes=filtro_mes, pago=filtro_pago))

        # Verificar se é edição ou inclusão
        movimentacao_id = request.form.get('movimentacao_id')
        data = request.form['data']
        data_pagamento = request.form['data_pagamento']
        descricao = request.form['descricao']

        categoria_id = request.form.get('categoria')
        categoria_nome = "Sem categoria"
        if categoria_id and categoria_id.isdigit():
            cursor.execute("SELECT nome FROM categorias WHERE id = ?", (categoria_id,))
            row = cursor.fetchone()
            if row:
                categoria_nome = row['nome']

        cartao_id = request.form['cartao']
        cartao_id = int(cartao_id) if cartao_id.isdigit() else None

        valor = float(request.form['valor'])
        tipo = request.form['tipo']
        parcelas = int(request.form.get('parcelas', 1))

        if movimentacao_id:  # UPDATE
            cursor.execute('''
                UPDATE movimentacoes
                SET data = ?, data_pagamento = ?, descricao = ?, categoria = ?, cartao = ?, valor = ?, tipo = ?, parcelas = ?
                WHERE id = ? AND usuario_id = ?
            ''', (data, data_pagamento, descricao, categoria_nome, cartao_id, valor, tipo, parcelas, movimentacao_id, usuario_id))
        else:  # INSERT
            cursor.execute('''
                INSERT INTO movimentacoes (data, data_pagamento, descricao, categoria, cartao, valor, tipo, parcelas, parcela_numero, paga, usuario_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?)
            ''', (data, data_pagamento, descricao, categoria_nome, cartao_id, valor, tipo, parcelas, usuario_id))

        conn.commit()
        return redirect(url_for('index', mes=filtro_mes, pago=filtro_pago))

    # Se for edição, carregar dados
    if edit_id:
        cursor.execute("SELECT * FROM movimentacoes WHERE id = ? AND usuario_id = ?", (edit_id, usuario_id))
        movimentacao_edit = cursor.fetchone()

    # Consulta das movimentações do usuário logado
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

    # Buscar categorias
    cursor.execute('SELECT id, nome, descricao FROM categorias ORDER BY descricao')
    categorias = cursor.fetchall()

    # Buscar cartões
    cursor.execute('SELECT id, nome, bandeira FROM cartoes ORDER BY nome')
    cartoes = cursor.fetchall()
    cartoes_dict = {c['id']: {'nome': c['nome'], 'bandeira': c['bandeira']} for c in cartoes}

    movimentacoes_formatadas = []
    for m in movimentacoes:
        try:
            cartao_id = int(m['cartao']) if m['cartao'] is not None else None
            cartao_info = cartoes_dict.get(cartao_id)
        except (ValueError, KeyError, TypeError):
            cartao_info = None

        movimentacoes_formatadas.append({
            'id': m['id'],
            'data': m['data'],
            'data_pagamento': m['data_pagamento'],
            'descricao': m['descricao'],
            'categoria': m['categoria'],
            'cartao': cartao_info,
            'valor': m['valor'],
            'tipo': m['tipo'],
            'parcelas': m['parcelas'] if 'parcelas' in m.keys() else 1,
            'parcela_numero': m['parcela_numero'] if 'parcela_numero' in m.keys() else 1,
            'paga': bool(m['paga']) if 'paga' in m.keys() else False
        })

    # Totais
    total = sum(m['valor'] if m['tipo'] == 'receita' else -m['valor'] for m in movimentacoes_formatadas)
    total_receitas = sum(m['valor'] for m in movimentacoes_formatadas if m['tipo'] == 'receita')
    total_despesas = sum(m['valor'] for m in movimentacoes_formatadas if m['tipo'] == 'despesa')

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
        usuario=session['usuario'],
        movimentacao_edit=movimentacao_edit
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

    # Pega ID do usuário logado
    cursor.execute("SELECT id FROM usuarios WHERE username = ?", (session['usuario'],))
    usuario_id = cursor.fetchone()['id']

    filtro_mes = request.args.get('mes')
    query = "SELECT * FROM movimentacoes WHERE usuario_id = ?"
    params = [usuario_id]
    if filtro_mes:
        query += " AND strftime('%Y-%m', data) = ?"
        params.append(filtro_mes)

    cursor.execute(query, params)
    movimentacoes = cursor.fetchall()

    categorias_totais = defaultdict(float)
    cartoes_despesas = defaultdict(float)
    cartoes_receitas = defaultdict(float)

    # Busca mapa de cartões (id -> nome)
    cursor.execute('SELECT id, nome FROM cartoes ORDER BY nome')
    cartoes_map = {row['id']: row['nome'] for row in cursor.fetchall()}

    # Filtra movimentações que possuem cartão válido ou cartão é None
    movimentacoes_validas = [m for m in movimentacoes if m['cartao'] in cartoes_map or m['cartao'] is None]

    for m in movimentacoes_validas:
        valor = m['valor']
        tipo = m['tipo']
        cartao_id = m['cartao']
        if tipo == 'despesa':
            categorias_totais[m['categoria']] += valor
            if cartao_id is not None:
                cartoes_despesas[cartao_id] += valor
        elif tipo == 'receita':
            if cartao_id is not None:
                cartoes_receitas[cartao_id] += valor

    # Lista completa dos cartões que aparecem (unificando despesas e receitas)
    todos_cartoes_ids = sorted(set(list(cartoes_despesas.keys()) + list(cartoes_receitas.keys())))

    # Aqui garantimos que labels_cartoes são os nomes, e não os IDs
    labels_cartoes = [cartoes_map.get(cid, f"Cartão {cid}") for cid in todos_cartoes_ids]
    valores_despesas = [cartoes_despesas.get(cid, 0) for cid in todos_cartoes_ids]
    valores_receitas = [cartoes_receitas.get(cid, 0) for cid in todos_cartoes_ids]

    labels_categorias = list(categorias_totais.keys())
    valores_categorias = list(categorias_totais.values())

    conn.close()

    return render_template('resumo.html',
                           labels_cartoes=labels_cartoes,
                           valores_despesas=valores_despesas,
                           valores_receitas=valores_receitas,
                           labels_categorias=labels_categorias,
                           valores_categorias=valores_categorias,
                           filtro_mes=filtro_mes,
                           usuario=session['usuario'])


# ==============================
# RUN
# ==============================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)