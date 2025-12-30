import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from database import get_connection
from config import UPLOAD_EMPRESA
from permissoes import tela_necessaria

empresa_bp = Blueprint(
    "empresa",
    __name__,
    url_prefix="/empresa",
    template_folder="templates/empresa"
)

@empresa_bp.route("/", methods=["GET", "POST"])
@tela_necessaria("empresa")
def painel_empresa():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT TOP 1 * FROM empresa")
    empresa = cursor.fetchone()

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        cnpj = request.form.get("cnpj", "").strip()
        endereco = request.form.get("endereco", "").strip()
        telefone = request.form.get("telefone", "").strip()

        logo = empresa.logo if empresa else None

        # ================= GARANTE PASTA =================
        os.makedirs(UPLOAD_EMPRESA, exist_ok=True)

        # ================= UPLOAD DA LOGO =================
        if "logo" in request.files:
            file = request.files["logo"]
            if file and file.filename:
                filename = secure_filename(file.filename)

                # evita sobrescrever arquivos
                nome_base, ext = os.path.splitext(filename)
                filename = f"{nome_base}_empresa{ext}"

                caminho_fisico = os.path.join(UPLOAD_EMPRESA, filename)
                file.save(caminho_fisico)

                # caminho salvo no banco (relativo)
                logo = f"static/uploads/empresa/{filename}"

        # ================= UPDATE / INSERT =================
        if empresa:
            cursor.execute("""
                UPDATE empresa
                SET nome = ?, cnpj = ?, endereco = ?, telefone = ?, logo = ?
            """, (nome, cnpj, endereco, telefone, logo))
        else:
            cursor.execute("""
                INSERT INTO empresa (nome, cnpj, endereco, telefone, logo)
                VALUES (?, ?, ?, ?, ?)
            """, (nome, cnpj, endereco, telefone, logo))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Dados da empresa atualizados com sucesso!", "success")
        return redirect(url_for("empresa.painel_empresa"))

    cursor.close()
    conn.close()

    return render_template("empresa/painel.html", empresa=empresa)