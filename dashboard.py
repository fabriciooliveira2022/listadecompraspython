from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from database import get_connection
import json

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

# ==================== DASHBOARD ====================
@dashboard_bp.route("/")
def dashboard_home():

    # 🔒 APENAS VERIFICA SE ESTÁ LOGADO
    if "user_id" not in session:
        flash("Faça login para continuar.", "warning")
        return redirect(url_for("usuarios.login"))

    mes = request.args.get("mes")  # YYYY-MM
    conn = get_connection()
    cursor = conn.cursor()

    # ---------------- FILTRO DATA ----------------
    ano = mes_num = None
    if mes:
        try:
            ano, mes_num = map(int, mes.split("-"))
        except ValueError:
            mes = None

    def filtro(col):
        if ano and mes_num:
            return f"YEAR({col}) = {ano} AND MONTH({col}) = {mes_num}"
        return "1=1"

    # ---------------- TOTAL PEDIDOS ----------------
    cursor.execute(f"SELECT COUNT(*) FROM Pedidos WHERE {filtro('data')}")
    total_pedidos = int(cursor.fetchone()[0] or 0)

     # ---------------- TOTAL PRODUTOS CADASTRADOS ----------------
    cursor.execute("SELECT COUNT(*) FROM Produtos")
    total_produtos = int(cursor.fetchone()[0] or 0)

    # ---------------- TOTAL CLIENTES CADASTRADOS ----------------
    cursor.execute("SELECT COUNT(*) FROM Clientes")
    total_clientes = int(cursor.fetchone()[0] or 0)

    # ---------------- FATURAMENTO ----------------
    cursor.execute(f"SELECT SUM(total) FROM Pedidos WHERE {filtro('data')}")
    faturamento_mes = float(cursor.fetchone()[0] or 0)

    # ---------------- COMPRA MAIS BARATA ----------------
    cursor.execute(f"""
        SELECT TOP 1 total, FORMAT(data, 'MM/yyyy')
        FROM Pedidos
        WHERE {filtro('data')}
        ORDER BY total ASC
    """)
    row = cursor.fetchone()
    compra_mais_barata = {
        "valor": float(row[0]) if row else 0.0,
        "mes": row[1] if row else "-"
    }

    # ---------------- CLIENTE QUE MAIS COMPRA ----------------
    cursor.execute(f"""
        SELECT TOP 1 c.nome, COUNT(p.id) AS total_compras, SUM(p.total) AS valor_total
        FROM Pedidos p
        INNER JOIN Clientes c ON c.id = p.cliente_id
        WHERE {filtro('p.data')}
        GROUP BY c.nome
        ORDER BY SUM(p.total) DESC
    """)
    row = cursor.fetchone()
    cliente_top = {
        "nome": row[0] if row else "-",
        "compras": int(row[1]) if row else 0,
        "valor": float(row[2]) if row else 0.0
    }

    # ---------------- TOP PRODUTOS ----------------
    cursor.execute(f"SELECT produtos FROM Pedidos WHERE {filtro('data')}")
    rows = cursor.fetchall() or []

    produtos = {}
    for r in rows:
        if not r[0]:
            continue
        try:
            itens = json.loads(r[0])
        except Exception:
            continue

        for item in itens:
            nome = item.get("nome")
            qtd = int(item.get("quantidade", 0))
            preco = float(item.get("preco", 0))
            if not nome:
                continue
            if nome not in produtos:
                produtos[nome] = {"qtd": 0, "valor": 0.0}
            produtos[nome]["qtd"] += qtd
            produtos[nome]["valor"] += qtd * preco

    top_produtos = sorted(produtos.items(), key=lambda x: x[1]["qtd"], reverse=True)[:5]
    top_produtos = [(nome, dados["qtd"], float(dados["valor"])) for nome, dados in top_produtos]

    # ---------------- PRODUTOS (PIE) ----------------
    pedidos_dia = [(nome, float(dados["valor"])) for nome, dados in produtos.items()]

    # ---------------- PEDIDOS POR MÊS ----------------
    cursor.execute("""
        SELECT FORMAT(data, 'MM/yyyy'), SUM(total)
        FROM Pedidos
        GROUP BY FORMAT(data, 'MM/yyyy')
        ORDER BY MIN(data)
    """)
    pedidos_mes = [(str(r[0]), float(r[1] or 0)) for r in cursor.fetchall()]

    # ---------------- FORMAS DE PAGAMENTO ----------------
    cursor.execute(f"""
        SELECT pagamento, SUM(total)
        FROM Pedidos
        WHERE {filtro('data')}
        GROUP BY pagamento
    """)
    pagamentos = [(str(r[0]), float(r[1] or 0)) for r in cursor.fetchall()]

    conn.close()

    return render_template(
        "dashboard.html",
        total_pedidos=total_pedidos,
        faturamento_mes=faturamento_mes,
        compra_mais_barata=compra_mais_barata,
        cliente_top=cliente_top,
        top_produtos=top_produtos,
        pedidos_dia=pedidos_dia,
        pedidos_mes=pedidos_mes,
        pagamentos=pagamentos,
        mes_selecionado=mes,
        total_produtos=total_produtos,
        total_clientes=total_clientes
    )