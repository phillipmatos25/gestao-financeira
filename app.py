from flask import Flask, render_template, request, redirect, url_for
from collections import defaultdict
from datetime import datetime
import sqlite3
from dateutil.relativedelta import relativedelta  # pip install python-dateutil

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/cadastros', methods=['GET', 'POST'])
def cadastros():
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

    cursor.execute('SELECT * FROM categorias')
    categorias = cursor.fetchall()

    cursor.execute('SELECT * FROM cartoes')
    cartoes = cursor.fetchall()

    conn.close()
    return render_template('cadastros.html', categorias=categorias, cartoes=cartoes)

@app.template_filter('format_currency')
def format_currency(valor):
    return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

@app.route('/', methods=['GET', 'POST'])
def index():
    mes_atual = datetime.now().strftime('%Y-%m')
    filtro_mes = request.args.get('mes')
    filtro_pago = request.args.get('pago')

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        if 'excluir_movimentacao' in request.form:
            movimentacao_id = request.form['movimentacao_id']
            cursor.execute('DELETE FROM movimentacoes WHERE id = ?', (movimentacao_id,))
            conn.commit()
            return redirect(url_for('index', mes=filtro_mes, pago=filtro_pago))

        if 'alterar_status_parcela' in request.form:
            movimentacao_id = request.form['movimentacao_id']
            paga_novo = int(request.form['paga'])
            cursor.execute('UPDATE movimentacoes SET paga = ? WHERE id = ?', (paga_novo, movimentacao_id))
            conn.commit()
            return redirect(url_for('index', mes=filtro_mes, pago=filtro_pago))

        data_str = request.form['data']
        data_pagamento_str = request.form.get('data_pagamento')
        data_pagamento = data_pagamento_str if data_pagamento_str else None

        descricao = request.form['descricao']
        categoria = request.form['categoria']
        cartao_id = request.form['cartao']
        cartao_id = int(cartao_id) if cartao_id.isdigit() else None
        valor_total = float(request.form['valor'])
        tipo = request.form['tipo']
        parcelas = int(request.form.get('parcelas', 1))
        fixa = request.form.get('fixa') == '1'  # Checkbox marcada?

        data_obj = datetime.strptime(data_str, '%Y-%m-%d')

        if fixa:
            for i in range(12):
                data_parcela = data_obj + relativedelta(months=i)
                cursor.execute('''
                    INSERT INTO movimentacoes 
                    (data, data_pagamento, descricao, categoria, cartao, valor, tipo, parcelas, parcela_numero, paga)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ''', (
                    data_parcela.strftime('%Y-%m-%d'),
                    data_pagamento,
                    descricao,
                    categoria,
                    cartao_id,
                    valor_total,
                    tipo,
                    1,
                    1
                ))
        else:
            valor_parcela = round(valor_total / parcelas, 2)
            valor_total_parcelas = valor_parcela * parcelas
            diferenca = round(valor_total - valor_total_parcelas, 2)

            for i in range(parcelas):
                data_parcela = data_obj + relativedelta(months=i)
                valor_atual = valor_parcela
                if i == parcelas - 1:
                    valor_atual = round(valor_parcela + diferenca, 2)

                cursor.execute('''
                    INSERT INTO movimentacoes 
                    (data, data_pagamento, descricao, categoria, cartao, valor, tipo, parcelas, parcela_numero, paga)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ''', (
                    data_parcela.strftime('%Y-%m-%d'),
                    data_pagamento,
                    descricao,
                    categoria,
                    cartao_id,
                    valor_atual,
                    tipo,
                    parcelas,
                    i + 1
                ))

        conn.commit()
        return redirect(url_for('index', mes=filtro_mes, pago=filtro_pago))

    query = "SELECT * FROM movimentacoes"
    params = []
    filtros = []
    if filtro_mes:
        filtros.append("strftime('%Y-%m', data) = ?")
        params.append(filtro_mes)
    if filtro_pago == 'sim':
        filtros.append("paga = 1")
    elif filtro_pago == 'nao':
        filtros.append("paga = 0")
    if filtros:
        query += " WHERE " + " AND ".join(filtros)
    query += " ORDER BY data"

    cursor.execute(query, params)
    movimentacoes = cursor.fetchall()

    cursor.execute('SELECT descricao FROM categorias order by descricao')
    categorias = cursor.fetchall()

    cursor.execute('SELECT id, nome, bandeira FROM cartoes order by nome')
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
            'descricao': m['descricao'],
            'categoria': m['categoria'],
            'cartao': cartao_info,
            'valor': m['valor'],
            'tipo': m['tipo'],
            'parcelas': m['parcelas'] if 'parcelas' in m.keys() else 1,
            'parcela_numero': m['parcela_numero'] if 'parcela_numero' in m.keys() else 1,
            'paga': bool(m['paga']) if 'paga' in m.keys() else False
        })

    total = sum(m['valor'] if m['tipo'] == 'receita' else -m['valor'] for m in movimentacoes_formatadas)
    total_receitas = sum(m['valor'] for m in movimentacoes_formatadas if m['tipo'] == 'receita')
    total_despesas = sum(m['valor'] for m in movimentacoes_formatadas if m['tipo'] == 'despesa')

    meses = []
    dados_por_mes = defaultdict(lambda: {'receitas': 0, 'despesas': 0})
    for m in movimentacoes_formatadas:
        data = datetime.strptime(m['data'], '%Y-%m-%d')
        mes_nome = data.strftime('%b')
        if mes_nome not in meses:
            meses.append(mes_nome)

        if m['tipo'] == 'receita':
            dados_por_mes[mes_nome]['receitas'] += m['valor']
        else:
            dados_por_mes[mes_nome]['despesas'] += m['valor']

    receitas = [dados_por_mes[mes]['receitas'] for mes in meses]
    despesas = [dados_por_mes[mes]['despesas'] for mes in meses]
    filtro_ano = datetime.now().year

    conn.close()

    return render_template(
        'index.html',
        movimentacoes=movimentacoes_formatadas,
        categorias=categorias,
        cartoes=cartoes,
        total=total,
        total_receitas=total_receitas,
        total_despesas=total_despesas,
        meses=meses,
        receitas=receitas,
        despesas=despesas,
        filtro_mes=filtro_mes,
        filtro_pago=filtro_pago,
        filtro_ano=filtro_ano
    )

@app.route('/resumo')
def resumo():
    filtro_mes = request.args.get('mes')
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM movimentacoes"
    params = []
    if filtro_mes:
        query += " WHERE strftime('%Y-%m', data) = ?"
        params.append(filtro_mes)

    cursor.execute(query, params)
    movimentacoes = cursor.fetchall()

    categorias_totais = defaultdict(float)
    cartoes_despesas = defaultdict(float)
    cartoes_receitas = defaultdict(float)

    cursor.execute('SELECT id, nome FROM cartoes order by nome')
    cartoes_map = {row['id']: row['nome'] for row in cursor.fetchall()}

    for m in movimentacoes:
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

    todos_cartoes_ids = sorted(set(list(cartoes_despesas.keys()) + list(cartoes_receitas.keys())))

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
                           filtro_mes=filtro_mes)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)