from flask import Flask, render_template, request, redirect, url_for
from collections import defaultdict
from datetime import datetime
import sqlite3

app = Flask(__name__)

# Filtro para formatar como moeda BR
@app.template_filter('format_currency')
def format_currency(valor):
    return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

cartoes = ["Nubank", "Caixa", "Santander"]
categorias = ["Mercado", "Restaurante", "Presente", "Loja", "Salário"]

@app.route('/', methods=['GET', 'POST'])
def index():
    filtro_mes = request.args.get('mes')  # formato: "mm"

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        data = request.form['data']
        descricao = request.form['descricao']
        categoria = request.form['categoria']
        cartao = request.form['cartao']
        valor = float(request.form['valor'])
        tipo = request.form['tipo']

        cursor.execute('''
            INSERT INTO movimentacoes (data, descricao, categoria, cartao, valor, tipo)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (data, descricao, categoria, cartao, valor, tipo))
        conn.commit()

        return redirect(url_for('index', mes=filtro_mes) if filtro_mes else url_for('index'))

    if filtro_mes:
        cursor.execute("SELECT * FROM movimentacoes WHERE strftime('%m', data) = ?", (filtro_mes,))
    else:
        cursor.execute("SELECT * FROM movimentacoes")

    movimentacoes = cursor.fetchall()
    conn.close()

    # Converte os resultados para lista de dicionários
    movimentacoes_formatadas = [
        {
            'data': m[1],
            'descricao': m[2],
            'categoria': m[3],
            'cartao': m[4],
            'valor': m[5],
            'tipo': m[6]
        }
        for m in movimentacoes
    ]

    total = sum(m['valor'] if m['tipo'] == 'receita' else -m['valor'] for m in movimentacoes_formatadas)
    total_receitas = sum(m['valor'] for m in movimentacoes_formatadas if m['tipo'] == 'receita')
    total_despesas = sum(m['valor'] for m in movimentacoes_formatadas if m['tipo'] == 'despesa')

    # Gráfico
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
    filtro_ano = filtro_mes.split('-')[0] if filtro_mes else datetime.now().year

    return render_template(
        'index.html',
        movimentacoes=movimentacoes_formatadas,
        categorias=categorias,
        cartoes=cartoes,
        filtro_mes=filtro_mes,
        filtro_ano=filtro_ano,
        meses=meses,
        receitas=receitas,
        despesas=despesas,
        total=total,
        total_receitas=total_receitas,
        total_despesas=total_despesas
    )

if __name__ == '__main__':
    app.run(debug=True)