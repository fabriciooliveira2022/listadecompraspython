from flask import Blueprint, render_template, request, redirect, url_for, flash
import json
from database import get_connection
from empresa import empresa
from permissoes import tela_necessaria

pedidos_bp = Blueprint("pedidos", __name__, url_prefix="/pedidos")

STATUS_PAGO = "PAGO"

# =====================================================
# FUNÇÕES AUXILIARES
# =====================================================
def to_float(valor):
    try:
        return float(str(valor).replace(",", "."))
    except:
        return 0.0

def get_nome_produto(cursor, produto_id):
    cursor.execute("SELECT nome FROM Produtos WHERE id = ?", (produto_id,))
    row = cursor.fetchone()
    return row.nome if row else None


# =====================================================
# LISTAR
# =====================================================
@pedidos_bp.route("/")
@tela_necessaria("Pedidos")
def pedidos_lista():
    with get_connection() as conn:
        cursor = conn.cursor()

        data_inicio = request.args.get("data_inicio")
        data_fim = request.args.get("data_fim")
        hoje = request.args.get("hoje")
        cliente_id = request.args.get("cliente_id")
        pagamento = request.args.get("pagamento")

        query = """
            SELECT p.id, p.data, c.nome AS cliente_nome,
                   p.pagamento, p.status,
                   p.produtos, p.total_bruto, p.desconto, p.total
            FROM Pedidos p
            JOIN Clientes c ON c.id = p.cliente_id
            WHERE 1=1
        """
        params = []

        # ================= FILTRO DATA =================
        if hoje == "1":
            query += " AND CONVERT(date, p.data) = CONVERT(date, GETDATE())"
        else:
            if data_inicio:
                query += " AND CONVERT(date, p.data) >= ?"
                params.append(data_inicio)

            if data_fim:
                query += " AND CONVERT(date, p.data) <= ?"
                params.append(data_fim)

        # ================= OUTROS FILTROS =================
        if cliente_id:
            query += " AND p.cliente_id = ?"
            params.append(cliente_id)

        if pagamento:
            query += " AND p.pagamento = ?"
            params.append(pagamento)

        query += " ORDER BY p.id DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        pedidos = []
        total_filtrado = 0.0

        for row in rows:
            produtos = json.loads(row.produtos or "[]")
            total = to_float(row.total)
            total_filtrado += total

            pedidos.append({
                "id": row.id,
                "cliente_nome": row.cliente_nome,
                "data": row.data,
                "pagamento": row.pagamento,
                "status": row.status,
                "produtos": produtos,
                "total_bruto": to_float(row.total_bruto),
                "desconto": to_float(row.desconto),
                "total": total
            })

        cursor.execute("SELECT id, nome FROM Clientes ORDER BY nome")
        clientes = cursor.fetchall()

    return render_template(
        "pedidos.html",
        pedidos=pedidos,
        clientes=clientes,
        total_filtrado=total_filtrado,
        data_inicio=data_inicio,
        data_fim=data_fim,
        cliente_id=cliente_id,
        pagamento=pagamento,
        empresa=empresa
    )

# =====================================================
# NOVO
# =====================================================
@pedidos_bp.route("/novo", methods=["GET", "POST"])
@tela_necessaria("Pedidos")
def pedidos_novo():
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id, nome FROM Clientes ORDER BY nome")
        clientes = cursor.fetchall()

        cursor.execute("SELECT id, nome, preco FROM Produtos ORDER BY nome")
        produtos = cursor.fetchall()

        if request.method == "POST":
            cliente_id = request.form.get("cliente_id")
            pagamento = request.form.get("pagamento")
            desconto = to_float(request.form.get("desconto"))

            produtos_json = []
            total_bruto = 0.0

            ids = request.form.getlist("produto_id[]")

            for pid in ids:
                qtd = int(request.form.get(f"quantidade_{pid}", 0))
                preco = to_float(request.form.get(f"preco_{pid}"))

                if qtd <= 0 or preco <= 0:
                    continue

                nome_produto = get_nome_produto(cursor, pid)
                if not nome_produto:
                    continue

                subtotal = qtd * preco
                total_bruto += subtotal

                produtos_json.append({
                    "id": int(pid),
                    "nome": nome_produto,
                    "quantidade": qtd,
                    "preco": preco,
                    "subtotal": subtotal
                })

            total_final = max(total_bruto - desconto, 0.0)

            cursor.execute("""
                INSERT INTO Pedidos
                (cliente_id, data, pagamento, status,
                 produtos, total_bruto, desconto, total)
                VALUES (?, GETDATE(), ?, ?, ?, ?, ?, ?)
            """, (
                cliente_id,
                pagamento,
                STATUS_PAGO,
                json.dumps(produtos_json, ensure_ascii=False),
                total_bruto,
                desconto,
                total_final
            ))

            conn.commit()
            flash("Pedido criado com sucesso!", "success")
            return redirect(url_for("pedidos.pedidos_lista"))

    return render_template(
        "pedidos_form.html",
        clientes=clientes,
        produtos=produtos,
        pedido=None
    )


# =====================================================
# EDITAR
# =====================================================
@pedidos_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@tela_necessaria("Pedidos")
def pedidos_editar(id):
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, cliente_id, pagamento, produtos, desconto, total_bruto
            FROM Pedidos WHERE id = ?
        """, (id,))
        row = cursor.fetchone()

        if not row:
            flash("Pedido não encontrado.", "warning")
            return redirect(url_for("pedidos.pedidos_lista"))

        cursor.execute("SELECT id, nome FROM Clientes ORDER BY nome")
        clientes = cursor.fetchall()

        cursor.execute("SELECT id, nome, preco FROM Produtos ORDER BY nome")
        produtos = cursor.fetchall()

        pedido = {
            "id": row.id,
            "cliente_id": row.cliente_id,
            "pagamento": row.pagamento,
            "desconto": to_float(row.desconto),
            "total_bruto": to_float(row.total_bruto),
            "produtos": json.loads(row.produtos or "[]")
        }

        if request.method == "POST":
            cliente_id = request.form.get("cliente_id")
            pagamento = request.form.get("pagamento")
            desconto = to_float(request.form.get("desconto"))

            produtos_editados = []
            total_bruto = 0.0

            ids = request.form.getlist("produto_id[]")

            for pid in ids:
                qtd = int(request.form.get(f"quantidade_{pid}", 0))
                preco = to_float(request.form.get(f"preco_{pid}"))

                if qtd <= 0 or preco <= 0:
                    continue

                nome_produto = get_nome_produto(cursor, pid)
                if not nome_produto:
                    continue

                subtotal = qtd * preco
                total_bruto += subtotal

                produtos_editados.append({
                    "id": int(pid),
                    "nome": nome_produto,
                    "quantidade": qtd,
                    "preco": preco,
                    "subtotal": subtotal
                })

            total_final = max(total_bruto - desconto, 0.0)

            cursor.execute("""
                UPDATE Pedidos SET
                    cliente_id = ?,
                    pagamento = ?,
                    produtos = ?,
                    total_bruto = ?,
                    desconto = ?,
                    total = ?
                WHERE id = ?
            """, (
                cliente_id,
                pagamento,
                json.dumps(produtos_editados, ensure_ascii=False),
                total_bruto,
                desconto,
                total_final,
                id
            ))

            conn.commit()
            flash("Pedido atualizado com sucesso!", "success")
            return redirect(url_for("pedidos.pedidos_lista"))

    return render_template(
        "pedidos_form.html",
        clientes=clientes,
        produtos=produtos,
        pedido=pedido
    )

# ================ FUNÇÃO CALCULAR TOTAIS ===================

def calcular_totais(produtos, desconto_tipo, desconto_valor):
    # Soma dos subtotais
    total_bruto = sum(p["subtotal"] for p in produtos)

    desconto = 0.0
    desconto_valor = desconto_valor or 0.0

    if desconto_tipo == "percentual":
        # Ex: 10% → 10 / 100
        desconto = total_bruto * (desconto_valor / 100)

    elif desconto_tipo == "valor":
        desconto = desconto_valor

    # Nunca permitir desconto maior que o total
    if desconto > total_bruto:
        desconto = total_bruto

    total_final = total_bruto - desconto

    return round(total_bruto, 2), round(desconto, 2), round(total_final, 2)

# =====================================================
# PEDIDO LIVRE - NOVO
# =====================================================
@pedidos_bp.route("/novo-livre", methods=["GET", "POST"])
@tela_necessaria("Pedidos")
def pedidos_livre():
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id, nome FROM Clientes ORDER BY nome")
        clientes = cursor.fetchall()

        if request.method == "POST":
            cliente_id = request.form.get("cliente_id")
            pagamento = request.form.get("pagamento")

            desconto_tipo = request.form.get("desconto_tipo")
            desconto_valor = to_float(request.form.get("desconto_valor"))

            nomes = request.form.getlist("produto_nome[]")
            qtds = request.form.getlist("produto_qtd[]")
            precos = request.form.getlist("produto_preco[]")

            produtos = []

            for nome, qtd, preco in zip(nomes, qtds, precos):
                nome = (nome or "").strip()
                qtd = int(qtd or 0)
                preco = to_float(preco)

                if not nome or qtd <= 0 or preco <= 0:
                    continue

                subtotal = qtd * preco

                produtos.append({
                    "id": None,
                    "nome": nome,
                    "quantidade": qtd,
                    "preco": preco,
                    "subtotal": subtotal
                })

            total_bruto, desconto, total = calcular_totais(
                produtos, desconto_tipo, desconto_valor
            )

            cursor.execute("""
                INSERT INTO Pedidos
                (cliente_id, data, pagamento, status,
                 produtos, total_bruto, desconto, total)
                VALUES (?, GETDATE(), ?, ?, ?, ?, ?, ?)
            """, (
                cliente_id,
                pagamento,
                STATUS_PAGO,
                json.dumps(produtos, ensure_ascii=False),
                total_bruto,
                desconto,
                total
            ))

            conn.commit()
            flash("Pedido criado com sucesso!", "success")
            return redirect(url_for("pedidos.pedidos_lista"))

    return render_template("pedido_livre.html", clientes=clientes)

# =====================================================
# PEDIDO LIVRE - EDITAR
# =====================================================
@pedidos_bp.route("/editar-livre/<int:id>", methods=["GET", "POST"])
@tela_necessaria("Pedidos")
def pedidos_livre_editar(id):
    with get_connection() as conn:
        cursor = conn.cursor()

        # Buscar pedido existente
        cursor.execute("SELECT * FROM Pedidos WHERE id = ?", (id,))
        pedido = cursor.fetchone()
        if not pedido:
            flash("Pedido não encontrado", "danger")
            return redirect(url_for("pedidos.pedidos_lista"))

        # Produtos existentes
        produtos_db = json.loads(pedido.produtos or "[]")

        # Clientes para select
        cursor.execute("SELECT id, nome FROM Clientes ORDER BY nome")
        clientes = cursor.fetchall()

        if request.method == "POST":
            cliente_id = request.form.get("cliente_id")
            pagamento = request.form.get("pagamento")
            desconto_valor = to_float(request.form.get("desconto_valor"))

            nomes = request.form.getlist("produto_nome[]")
            qtds = request.form.getlist("produto_qtd[]")
            precos = request.form.getlist("produto_preco[]")

            produtos = []
            for nome, qtd, preco in zip(nomes, qtds, precos):
                nome = (nome or "").strip()
                qtd = int(qtd or 0)
                preco = to_float(preco)
                if not nome or qtd <= 0 or preco <= 0:
                    continue
                subtotal = qtd * preco
                produtos.append({
                    "id": None,
                    "nome": nome,
                    "quantidade": qtd,
                    "preco": preco,
                    "subtotal": subtotal
                })

            # Calcular totais
            total_bruto = sum(p["subtotal"] for p in produtos)
            desconto = min(desconto_valor, total_bruto)
            total = total_bruto - desconto

            # **UPDATE** obrigatório
            cursor.execute("""
                UPDATE Pedidos SET
                    cliente_id = ?,
                    pagamento = ?,
                    produtos = ?,
                    total_bruto = ?,
                    desconto = ?,
                    total = ?
                WHERE id = ?
            """, (
                cliente_id,
                pagamento,
                json.dumps(produtos, ensure_ascii=False),
                total_bruto,
                desconto,
                total,
                id
            ))

            conn.commit()
            flash("Pedido atualizado com sucesso!", "success")
            return redirect(url_for("pedidos.pedidos_lista"))

    return render_template(
        "pedido_livre_editar.html",
        pedido=pedido,
        produtos=produtos_db,
        clientes=clientes,
        desconto_valor=to_float(pedido.desconto)
    )

# =====================================================
# RECIBO
# =====================================================
@pedidos_bp.route("/recibo/<int:id>")
@tela_necessaria("Pedidos")
def pedidos_recibo(id):
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT p.id, p.data, p.pagamento, p.total, p.desconto,
                   c.nome AS cliente_nome
            FROM Pedidos p
            JOIN Clientes c ON c.id = p.cliente_id
            WHERE p.id = ?
        """, (id,))
        pedido = cursor.fetchone()

        if not pedido:
            flash("Pedido não encontrado.", "warning")
            return redirect(url_for("pedidos.pedidos_lista"))

        cursor.execute("SELECT produtos FROM Pedidos WHERE id = ?", (id,))
        produtos = json.loads(cursor.fetchone().produtos or "[]")

    return render_template(
        "pedidos_recibo.html",
        pedido=pedido,
        produtos=produtos
    )


# =====================================================
# EXCLUIR
# =====================================================
@pedidos_bp.route("/excluir/<int:id>", methods=["POST"])
@tela_necessaria("Pedidos")
def pedidos_excluir(id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Pedidos WHERE id = ?", (id,))
        conn.commit()

    flash("Pedido excluído com sucesso!", "success")
    return redirect(url_for("pedidos.pedidos_lista"))