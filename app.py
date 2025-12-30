from flask import Flask, redirect, url_for, session, request
from database import get_connection

# ================= APP =================
app = Flask(__name__)
app.secret_key = "chave_secreta"

# ================= BLUEPRINTS =================
from clientes import clientes_bp
from produtos import produtos_bp
from pedidos import pedidos_bp
from dashboard import dashboard_bp
from usuarios import usuarios_bp
from empresa import empresa_bp

app.register_blueprint(usuarios_bp)
app.register_blueprint(clientes_bp)
app.register_blueprint(produtos_bp)
app.register_blueprint(pedidos_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(empresa_bp)

@app.context_processor
def inject_usuario():
    return {
        "usuario": session.get("usuario")
    }

# ================= CONTEXT PROCESSOR (EMPRESA) =================
@app.context_processor
def dados_empresa():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT TOP 1 nome, cnpj, logo
        FROM empresa
        WHERE ativo = 1
    """)
    empresa = cursor.fetchone()

    cursor.close()
    conn.close()

    return {
        "empresa_nome": empresa.nome if empresa else "",
        "empresa_cnpj": empresa.cnpj if empresa else "",
        "empresa_logo": empresa.logo if empresa else ""
    }

# ================= LOGIN OBRIGATÓRIO =================
@app.before_request
def proteger_rotas():
    rotas_livres = (
        "usuarios.login",
        "usuarios.alterar_senha",
    )

    rota_atual = request.endpoint

    if rota_atual is None:
        return

    if rota_atual.startswith("static"):
        return

    if rota_atual in rotas_livres:
        return

    if "user_id" not in session:
        return redirect(url_for("usuarios.login"))

# ================= PÁGINA INICIAL =================
@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("usuarios.login"))
    return redirect(url_for("dashboard.dashboard_home"))

if __name__ == "__main__":
    app.run(debug=True)