from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from usuarios import usuarios_bp
import pyodbc

# -------- CONEXÃO SQL SERVER --------
def get_conn():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=DESKTOP-URUJPEC\SQLEXPRESS;"
        "DATABASE=listadecompras;"
        "Trusted_Connection=yes;"
    )

# ===================== LOGIN =====================
@usuarios_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]

        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT id, nome, senha FROM usuarios WHERE email = ?", (email,))
        usuario = cursor.fetchone()

        if usuario and check_password_hash(usuario[2], senha):
            session["user_id"] = usuario[0]
            session["user_nome"] = usuario[1]
            return redirect(url_for("dashboard.dashboard_home"))
        else:
            flash("Email ou senha incorretos!")

    return render_template("usuarios/login.html")

# ===================== LOGOUT =====================
@usuarios_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("usuarios.login"))

# ===================== NOVO USUÁRIO =====================
@usuarios_bp.route("/usuarios/novo", methods=["GET", "POST"])
def usuarios_novo():
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        senha = generate_password_hash(request.form["senha"])

        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO usuarios (nome, email, senha)
            VALUES (?, ?, ?)
        """, (nome, email, senha))

        conn.commit()
        flash("Usuário criado com sucesso!")
        return redirect(url_for("usuarios.login"))

    return render_template("usuarios/usuarios_novo.html")

# ===================== ALTERAR SENHA (ESQUECI) =====================
@usuarios_bp.route("/usuarios/alterar_senha", methods=["GET", "POST"])
def alterar_senha():
    if request.method == "POST":
        email = request.form["email"]
        nova_senha = generate_password_hash(request.form["nova_senha"])

        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("UPDATE usuarios SET senha=? WHERE email=?", (nova_senha, email))
        conn.commit()

        flash("Senha alterada com sucesso!")
        return redirect(url_for("usuarios.login"))

    return render_template("usuarios/alterar_senha.html")

# ===================== MINHA SENHA (DENTRO DO SISTEMA) =====================
@usuarios_bp.route("/usuarios/minha_senha", methods=["GET", "POST"])
def minha_senha():
    if "user_id" not in session:
        return redirect(url_for("usuarios.login"))

    if request.method == "POST":
        senha_atual = request.form["senha_atual"]
        nova_senha = generate_password_hash(request.form["nova_senha"])

        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT senha FROM usuarios WHERE id=?", (session["user_id"],))
        usuario = cursor.fetchone()

        if not usuario or not check_password_hash(usuario[0], senha_atual):
            flash("Senha atual incorreta!")
            return redirect(url_for("usuarios.minha_senha"))

        cursor.execute("UPDATE usuarios SET senha=? WHERE id=?", (nova_senha, session["user_id"]))
        conn.commit()

        flash("Senha alterada com sucesso!")
        return redirect(url_for("dashboard.dashboard_home"))

    return render_template("usuarios/minha_senha.html")