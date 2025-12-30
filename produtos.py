import csv
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_connection
from permissoes import tela_necessaria

produtos_bp = Blueprint("produtos", __name__, url_prefix="/produtos")

# =====================================================
# LISTAR
# =====================================================
@produtos_bp.route("/")
@tela_necessaria("Produtos")
def produtos_lista():
    pagina = request.args.get("page", 1, type=int)
    por_pagina = 10

    filtro_nome = request.args.get("nome", "")
    ordenar = request.args.get("ordenar", "nome")
    direcao = request.args.get("direcao", "asc")

    offset = (pagina - 1) * por_pagina
    ordem_sql = "ASC" if direcao == "asc" else "DESC"

    where_sql = ""
    params = []

    if filtro_nome:
        where_sql = "WHERE nome LIKE ?"
        params.append(f"%{filtro_nome}%")

    with get_connection() as conn:
        cursor = conn.cursor()

        # Total
        cursor.execute(
            f"SELECT COUNT(*) FROM Produtos {where_sql}",
            params
        )
        total = cursor.fetchone()[0]

        # Lista paginada
        cursor.execute(
            f"""
            SELECT id, nome, preco
            FROM Produtos
            {where_sql}
            ORDER BY {ordenar} {ordem_sql}
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """,
            params + [offset, por_pagina]
        )

        produtos = cursor.fetchall()

    total_paginas = (total + por_pagina - 1) // por_pagina

    inicio = offset + 1 if total > 0 else 0
    fim = min(offset + por_pagina, total)

    return render_template(
        "produtos.html",
        produtos=produtos,
        pagina=pagina,
        total_paginas=total_paginas,
        filtro_nome=filtro_nome,
        ordenar=ordenar,
        direcao=direcao,
        total=total,
        inicio=inicio,
        fim=fim
    )

# =====================================================
# CRIAR
# =====================================================
@produtos_bp.route("/novo", methods=["GET", "POST"])
@tela_necessaria("Produtos")
def produtos_novo():
    if request.method == "POST":
        nome = request.form.get("nome")
        preco = request.form.get("preco")

        if not nome or not preco:
            flash("Preencha todos os campos.", "warning")
            return render_template("produtos_form.html")

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Produtos (nome, preco) VALUES (?, ?)",
                (nome, preco)
            )
            conn.commit()

        flash("Produto criado com sucesso!", "success")
        return redirect(url_for("produtos.produtos_lista"))

    return render_template("produtos_form.html")


# =====================================================
# EDITAR
# =====================================================
@produtos_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@tela_necessaria("Produtos")
def produtos_editar(id):
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, nome, preco FROM Produtos WHERE id = ?",
            (id,)
        )
        produto = cursor.fetchone()

        if not produto:
            flash("Produto não encontrado.", "warning")
            return redirect(url_for("produtos.produtos_lista"))

        if request.method == "POST":
            nome = request.form.get("nome")
            preco = request.form.get("preco")

            if not nome or not preco:
                flash("Preencha todos os campos.", "warning")
                return render_template("produtos_form.html", produto=produto)

            cursor.execute(
                "UPDATE Produtos SET nome = ?, preco = ? WHERE id = ?",
                (nome, preco, id)
            )
            conn.commit()

            flash("Produto atualizado com sucesso!", "success")
            return redirect(url_for("produtos.produtos_lista"))

    return render_template("produtos_form.html", produto=produto)


# =====================================================
# EXCLUIR
# =====================================================
@produtos_bp.route("/excluir/<int:id>", methods=["POST"])
@tela_necessaria("Produtos")
def produtos_excluir(id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Produtos WHERE id = ?", (id,))
        conn.commit()

    flash("Produto excluído com sucesso!", "success")
    return redirect(url_for("produtos.produtos_lista"))

# ==========================================
# IMPORTAR PRODUTOS VIA CSV (SEM DUPLICAR)
# ==========================================
@produtos_bp.route("/importar", methods=["GET", "POST"])
def importar_csv():
    if request.method == "POST":
        arquivo = request.files.get("arquivo")

        if not arquivo or arquivo.filename == "":
            flash("Selecione um arquivo CSV.", "danger")
            return redirect(request.url)

        if not arquivo.filename.lower().endswith(".csv"):
            flash("O arquivo deve estar no formato CSV.", "danger")
            return redirect(request.url)

        try:
            # 🔹 Corrige acentuação do Excel (UTF-8 com BOM)
            stream = io.StringIO(
                arquivo.stream.read().decode("utf-8-sig")
            )
            leitor = csv.DictReader(stream, delimiter=";")

            conn = get_connection()
            cursor = conn.cursor()

            inseridos = 0
            atualizados = 0

            for linha in leitor:
                nome = linha.get("nome")
                preco = linha.get("preco")

                if not nome or not preco:
                    continue

                nome = nome.strip()
                preco = preco.replace(",", ".")

                try:
                    preco = float(preco)
                except ValueError:
                    continue

                # 🔎 Verifica se produto já existe
                cursor.execute(
                    "SELECT id FROM produtos WHERE nome = ?",
                    (nome,)
                )
                produto = cursor.fetchone()

                if produto:
                    # ✏️ Atualiza produto existente
                    cursor.execute("""
                        UPDATE produtos
                        SET preco = ?
                        WHERE id = ?
                    """, (preco, produto.id))

                    atualizados += 1
                else:
                    # ➕ Insere novo produto
                    cursor.execute("""
                        INSERT INTO produtos (nome, preco)
                        VALUES (?, ?)
                    """, (nome, preco))

                    inseridos += 1

            conn.commit()
            conn.close()

            flash(
                f"Importação concluída: "
                f"{inseridos} inseridos, {atualizados} atualizados.",
                "success"
            )
            return redirect(url_for("produtos.produtos_lista"))

        except Exception as e:
            flash(f"Erro ao importar CSV: {str(e)}", "danger")

    return render_template("importar_csv.html")