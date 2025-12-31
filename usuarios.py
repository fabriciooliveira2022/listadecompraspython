import pyodbc
import hashlib
import hmac

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

usuarios_bp = Blueprint(
    "usuarios",
    __name__,
    url_prefix="/usuarios",
    template_folder="templates/usuarios"
)

# ==================== NORMALIZAR HASH ====================
def normalizar_hash(valor):
    if not valor:
        return None

    if isinstance(valor, (bytes, bytearray)):
        valor = valor.decode("utf-8")

    elif hasattr(valor, "tobytes"):  # memoryview
        valor = valor.tobytes().decode("utf-8")

    return valor.strip()

# ==================== VERIFICAR SENHA (PBKDF2 + SCRYPT) ====================
def verificar_senha(senha_digitada, senha_hash):
    if not senha_digitada or not senha_hash:
        return False

    # PBKDF2 (Werkzeug / Flask padrão)
    if senha_hash.startswith("pbkdf2:"):
        return check_password_hash(senha_hash, senha_digitada)

    # SCRYPT (hash legado)
    if senha_hash.startswith("scrypt:"):
        try:
            # Ex: scrypt:32768:8:1$salt$hash
            _, params, resto = senha_hash.split("$", 2)
            salt, hash_salvo = resto.split("$")

            novo_hash = hashlib.scrypt(
                senha_digitada.encode("utf-8"),
                salt=salt.encode("utf-8"),
                n=32768,
                r=8,
                p=1
            ).hex()

            return hmac.compare_digest(novo_hash, hash_salvo)
        except Exception:
            return False

    return False

# ==================== CONFIGURAÇÃO SQL SERVER ====================
SERVER = r"DESKTOP-URUJPEC\SQLEXPRESS"
DATABASE = "listadecompras"
DRIVER = "ODBC Driver 17 for SQL Server"

def get_connection():
    return pyodbc.connect(
        f"DRIVER={{{DRIVER}}};SERVER={SERVER};DATABASE={DATABASE};Trusted_Connection=yes;"
    )

# ==================== CHECAR PERMISSÃO ====================
def tem_permissao(recurso: str) -> bool:
    """
    Verifica se o usuário logado tem permissão para acessar o recurso (tela).
    Admin sempre tem acesso a tudo.
    """
    if "user_id" not in session:
        return False  # não logado

    recurso = recurso.strip().lower()

    # Perfil Admin
    if session.get("perfil_id") == 1:
        return True

    # Checa se a tela está nas telas permitidas do perfil
    return recurso in session.get("telas", [])

# ==================== LOGIN ====================
@usuarios_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, nome, senha_hash, perfil_id, ativo
                FROM dbo.Usuarios
                WHERE email=?
            """, (email,))
            user = cursor.fetchone()

            if not user or user.ativo != 1 or not check_password_hash(user.senha_hash, senha):
                flash("Usuário ou senha inválidos.", "danger")
                return redirect(url_for("usuarios.login"))

            # Limpa sessão e salva dados do usuário
            session.clear()
            session["user_id"] = user.id
            session["user_nome"] = user.nome
            session["perfil_id"] = int(user.perfil_id)

            # Carrega telas permitidas para o perfil
            cursor.execute("SELECT tela_nome FROM dbo.PerfilTelas WHERE perfil_id = ?", (user.perfil_id,))
            telas = cursor.fetchall()
            session["telas"] = [row[0].strip().lower() for row in telas] if telas else []

            # Admin sempre tem todas as telas
            if user.perfil_id == 1:
                cursor.execute("SELECT DISTINCT tela_nome FROM dbo.PerfilTelas")
                admin_telas = cursor.fetchall()
                session["telas"] = [row[0].strip().lower() for row in admin_telas]

        return redirect(url_for("dashboard.dashboard_home"))

    return render_template("usuarios/login.html")

# ==================== LOGOUT ====================
@usuarios_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("usuarios.login"))

# ==================== ALTERAR SENHA (USUÁRIO LOGADO) ====================
@usuarios_bp.route("/alterar-senha", methods=["GET", "POST"])
def alterar_senha_usuario():
    if "user_id" not in session:
        return redirect(url_for("usuarios.login"))

    if request.method == "POST":
        senha = request.form["senha"]
        senha2 = request.form["senha2"]

        if senha != senha2 or len(senha) < 6:
            flash("A senha deve ter no mínimo 6 caracteres.", "danger")
            return redirect(url_for("usuarios.alterar_senha_usuario"))

        senha_hash = generate_password_hash(senha)

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE dbo.Usuarios
                SET senha_hash = ?
                WHERE id = ?
            """, (senha_hash, session["user_id"]))
            conn.commit()

        flash("Senha alterada com sucesso.", "success")
        return redirect(url_for("dashboard.dashboard_home"))

    return render_template("usuarios/alterar_senha.html")

# ==================== ALTERAR SENHA (ADMIN) ====================
@usuarios_bp.route("/alterar-senha/<int:id>", methods=["GET", "POST"])
def alterar_senha_admin(id):
    if not tem_permissao("usuarios"):
        flash("Sem permissão.", "danger")
        return redirect(url_for("dashboard.dashboard_home"))

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome FROM dbo.Usuarios WHERE id=?", (id,))
        usuario = cursor.fetchone()

        if not usuario:
            flash("Usuário não encontrado.", "danger")
            return redirect(url_for("usuarios.usuarios_listar"))

        if request.method == "POST":
            senha = request.form["senha"]
            senha2 = request.form["senha2"]

            if senha != senha2 or len(senha) < 6:
                flash("Senha inválida.", "danger")
                return redirect(url_for("usuarios.alterar_senha_admin", id=id))

            cursor.execute("""
                UPDATE dbo.Usuarios
                SET senha_hash=?
                WHERE id=?
            """, (generate_password_hash(senha), id))
            conn.commit()

            flash("Senha alterada com sucesso.", "success")
            return redirect(url_for("usuarios.usuarios_listar"))

    return render_template("usuarios/alterar_senha_admin.html", usuario=usuario)

# ==================== LISTAR USUÁRIOS ====================
@usuarios_bp.route("/")
def usuarios_listar():
    if not tem_permissao("usuarios"):
        flash("Sem permissão para acessar usuários.", "danger")
        return redirect(url_for("dashboard.dashboard_home"))

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nome, email, ativo, perfil_id
            FROM dbo.Usuarios
            ORDER BY nome
        """)
        usuarios = cursor.fetchall()

    return render_template("usuarios/usuarios_listar.html", usuarios=usuarios)

# ==================== NOVO USUÁRIO ====================
@usuarios_bp.route("/novo", methods=["GET", "POST"])
def usuarios_novo():
    if not tem_permissao("usuarios"):
        flash("Sem permissão para criar usuários.", "danger")
        return redirect(url_for("usuarios.usuarios_listar"))

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome FROM dbo.Perfis ORDER BY nome")
        perfis = cursor.fetchall()

    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        senha = request.form["senha"]
        senha2 = request.form["senha2"]
        perfil = int(request.form.get("perfil_id", 2))

        if senha != senha2 or len(senha) < 6:
            flash("Senha inválida.", "danger")
            return redirect(url_for("usuarios.usuarios_novo"))

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM dbo.Usuarios WHERE email=?", (email,))
            if cursor.fetchone():
                flash("Email já cadastrado.", "danger")
                return redirect(url_for("usuarios.usuarios_novo"))

            cursor.execute("""
                INSERT INTO dbo.Usuarios (nome, email, senha_hash, ativo, perfil_id)
                VALUES (?, ?, ?, 1, ?)
            """, (nome, email, generate_password_hash(senha), perfil))
            conn.commit()

        flash("Usuário criado com sucesso.", "success")
        return redirect(url_for("usuarios.usuarios_listar"))

    return render_template("usuarios/usuarios_novo.html", perfis=perfis)

# ==================== EDITAR USUÁRIO ====================
@usuarios_bp.route("/editar/<int:id>", methods=["GET", "POST"])
def usuarios_editar(id):
    if not tem_permissao("usuarios"):
        flash("Sem permissão.", "danger")
        return redirect(url_for("usuarios.usuarios_listar"))

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nome, email, perfil_id, ativo
            FROM dbo.Usuarios
            WHERE id=?
        """, (id,))
        usuario = cursor.fetchone()

        if not usuario:
            flash("Usuário não encontrado.", "danger")
            return redirect(url_for("usuarios.usuarios_listar"))

        cursor.execute("SELECT id, nome FROM dbo.Perfis ORDER BY nome")
        perfis = cursor.fetchall()

        if request.method == "POST":
            cursor.execute("""
                UPDATE dbo.Usuarios
                SET nome=?, email=?, perfil_id=?, ativo=?
                WHERE id=?
            """, (
                request.form["nome"],
                request.form["email"],
                int(request.form["perfil_id"]),
                int(request.form["ativo"]),
                id
            ))
            conn.commit()
            flash("Usuário atualizado.", "success")
            return redirect(url_for("usuarios.usuarios_listar"))

    return render_template("usuarios/usuarios_editar.html", usuario=usuario, perfis=perfis)

# ==================== EXCLUIR USUÁRIO ====================
@usuarios_bp.route("/excluir/<int:id>", methods=["POST"])
def usuarios_excluir(id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Usuarios WHERE id=?", (id,))
        conn.commit()

    flash("Usuário excluído com sucesso!", "success")
    return redirect(url_for("usuarios.usuarios_listar"))

# ============== PRIMEIRO USUÁRIO - TELA LOGIN ================
@usuarios_bp.route("/primeiro-usuario", methods=["GET", "POST"])
def primeiro_usuario():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome FROM dbo.Perfis ORDER BY nome")
        perfis = cursor.fetchall()

    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        senha = request.form["senha"]
        senha2 = request.form["senha2"]
        perfil = int(request.form.get("perfil_id", 2))

        if senha != senha2 or len(senha) < 6:
            flash("Senha inválida.", "danger")
            return redirect(url_for("usuarios.primeiro_usuario"))

        with get_connection() as conn:
            cursor = conn.cursor()

            # Impede email duplicado
            cursor.execute("SELECT id FROM dbo.Usuarios WHERE email=?", (email,))
            if cursor.fetchone():
                flash("Email já cadastrado.", "danger")
                return redirect(url_for("usuarios.primeiro_usuario"))

            cursor.execute("""
                INSERT INTO dbo.Usuarios
                (nome, email, senha_hash, ativo, perfil_id)
                VALUES (?, ?, ?, 1, ?)
            """, (
                nome,
                email,
                generate_password_hash(senha),
                perfil))
            
            conn.commit()

        flash("Usuário criado com sucesso.", "success")
        return redirect(url_for("usuarios.login"))

    return render_template("usuarios/primeiro_usuario.html", perfis=perfis)
