import csv
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_connection
from permissoes import tela_necessaria

clientes_bp = Blueprint("clientes", __name__, url_prefix="/clientes")

# ================= LISTAR =================
@clientes_bp.route("/")
@tela_necessaria("Clientes")
def clientes_lista():
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
            f"SELECT COUNT(*) FROM Clientes {where_sql}",
            params
        )
        total = cursor.fetchone()[0]

        # Lista
        cursor.execute(
            f"""
            SELECT id, nome, email, telefone
            FROM Clientes
            {where_sql}
            ORDER BY {ordenar} {ordem_sql}
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """,
            params + [offset, por_pagina]
        )

        clientes = cursor.fetchall()

    total_paginas = (total + por_pagina - 1) // por_pagina

    inicio = offset + 1 if total > 0 else 0
    fim = min(offset + por_pagina, total)

    return render_template(
        "clientes.html",
        clientes=clientes,
        pagina=pagina,
        total_paginas=total_paginas,
        filtro_nome=filtro_nome,
        ordenar=ordenar,
        direcao=direcao,
        total=total,
        inicio=inicio,
        fim=fim
    )

# ================= CRIAR =================
@clientes_bp.route("/novo", methods=["GET", "POST"])
@tela_necessaria("Clientes")
def clientes_novo():
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        telefone = request.form["telefone"]

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Clientes (nome, email, telefone) VALUES (?, ?, ?)",
                (nome, email, telefone)
            )
            conn.commit()

        flash("Cliente criado com sucesso!", "success")
        return redirect(url_for("clientes.clientes_lista"))

    return render_template("clientes_form.html")

# ================= EDITAR =================
@clientes_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@tela_necessaria("Clientes")
def clientes_editar(id):
    with get_connection() as conn:
        cursor = conn.cursor()

        if request.method == "POST":
            nome = request.form["nome"]
            email = request.form["email"]
            telefone = request.form["telefone"]

            cursor.execute(
                "UPDATE Clientes SET nome=?, email=?, telefone=? WHERE id=?",
                (nome, email, telefone, id)
            )
            conn.commit()

            flash("Cliente atualizado com sucesso!", "success")
            return redirect(url_for("clientes.clientes_lista"))

        cursor.execute(
            "SELECT id, nome, email, telefone FROM Clientes WHERE id=?",
            (id,)
        )
        cliente = cursor.fetchone()

    return render_template("clientes_form.html", cliente=cliente)

# ================= EXCLUIR =================
@clientes_bp.route("/excluir/<int:id>", methods=["POST"])
@tela_necessaria("Clientes")
def clientes_excluir(id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Clientes WHERE id=?", (id,))
        conn.commit()

    flash("Cliente excluído com sucesso!", "success")
    return redirect(url_for("clientes.clientes_lista"))

# ==========================================
# IMPORTAR CLIENTES VIA CSV (UPSERT)
# ==========================================
@clientes_bp.route("/importar", methods=["GET", "POST"])
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
                nome = (linha.get("nome") or "").strip()
                email = (linha.get("email") or "").strip().lower()
                telefone = (linha.get("telefone") or "").strip()

                if not nome or not email:
                    continue

                # 🔎 Verifica se cliente já existe (por email)
                cursor.execute(
                    "SELECT id FROM clientes WHERE email = ?",
                    (email,)
                )
                cliente = cursor.fetchone()

                if cliente:
                    # ✏️ Atualiza cliente existente
                    cursor.execute("""
                        UPDATE clientes
                        SET nome = ?, telefone = ?
                        WHERE id = ?
                    """, (nome, telefone, cliente.id))

                    atualizados += 1
                else:
                    # ➕ Insere novo cliente
                    cursor.execute("""
                        INSERT INTO clientes (nome, email, telefone)
                        VALUES (?, ?, ?)
                    """, (nome, email, telefone))

                    inseridos += 1

            conn.commit()
            conn.close()

            flash(
                f"Importação concluída: "
                f"{inseridos} novos, {atualizados} atualizados.",
                "success"
            )
            return redirect(url_for("clientes.clientes_lista"))

        except Exception as e:
            flash(f"Erro ao importar CSV: {str(e)}", "danger")

    return render_template("clientes_importar_csv.html")