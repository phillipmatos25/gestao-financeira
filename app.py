from flask import Flask, render_template, request, redirect, url_for
from collections import defaultdict
from datetime import datetime

app = Flask(__name__)

# Filtro para formatar como moeda BR
@app.template_filter('format_currency')
def format_currency(valor):
    return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

cartoes = ["Nubank", "Caixa", "Santander"]
categorias = ["Mercado", "Restaurante", "Presente", "Loja", "Salário"]
movimentacoes = []  # Armazenamento em memória por enquanto

@app.route('/', methods=['GET', 'POST'])
def index():
    filtro_mes = request.args.get('mes')  # formato: "mm"

    if request.method == 'POST':
        data = request.form['data']
        descricao = request.form['descricao']
        categoria = request.form['categoria']
        cartao = request.form['cartao']
        valor = float(request.form['valor'])
        tipo = request.form['tipo']

        movimentacoes.append({
            'data': data,
            'descricao': descricao,
            'categoria': categoria,
            'cartao': cartao,
            'valor': valor,
            'tipo': tipo
        })

        return redirect(url_for('index', mes=filtro_mes) if filtro_mes else url_for('index'))

    if filtro_mes:
        movimentacoes_filtradas = [
            m for m in movimentacoes if m['data'].startswith(filtro_mes)
        ]
    else:
        movimentacoes_filtradas = movimentacoes

    total = sum(m['valor'] if m['tipo'] == 'receita' else -m['valor'] for m in movimentacoes_filtradas)

    # 👇 NOVO: dados para gráfico
    meses = []
    dados_por_mes = defaultdict(lambda: {'receitas': 0, 'despesas': 0})

    for m in movimentacoes_filtradas:
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

    total_receitas = sum(m['valor'] for m in movimentacoes_filtradas if m['tipo'] == 'receita')
    total_despesas = sum(m['valor'] for m in movimentacoes_filtradas if m['tipo'] == 'despesa')

    return render_template(
        'index.html',
        movimentacoes=movimentacoes_filtradas,
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