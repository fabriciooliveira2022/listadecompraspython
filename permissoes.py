from flask import session, redirect, url_for, flash
from functools import wraps

def tela_necessaria(tela: str):
    """
    Decorator para proteger rotas baseado no PERFIL do usuário.

    Perfis:
    1 = Admin            -> acesso total
    2 = Usuário          -> apenas Pedidos
    3 = Usuário Avançado -> todas menos Usuários

    Evita loop de redirecionamento redirecionando o usuário para uma rota
    segura caso ele não tenha acesso à tela solicitada.
    """

    tela = tela.lower()  # padroniza para comparação

    # Rota segura padrão para redirecionamento
    rota_segura_por_perfil = {
        1: "dashboard.dashboard_home",  # Admin -> dashboard
        2: "pedidos.listar_pedidos",    # Usuário -> página de pedidos
        3: "dashboard.dashboard_home"   # Usuário avançado -> dashboard
    }

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # ================= NÃO LOGADO =================
            if "user_id" not in session:
                flash("Você precisa estar logado para acessar esta página.", "warning")
                return redirect(url_for("usuarios.login"))

            # ================= PERFIL =================
            try:
                perfil = int(session.get("perfil_id"))
            except (TypeError, ValueError):
                flash("Perfil de usuário inválido.", "danger")
                return redirect(url_for("usuarios.login"))

            # ================= ADMIN =================
            if perfil == 1:
                return func(*args, **kwargs)

            # ================= USUÁRIO =================
            if perfil == 2:
                if tela != "pedidos":
                    flash("Você não tem acesso a esta tela.", "danger")
                    return redirect(url_for(rota_segura_por_perfil[2]))
                return func(*args, **kwargs)

            # ================= USUÁRIO AVANÇADO =================
            if perfil == 3:
                if tela == "usuários":
                    flash("Você não tem acesso a esta tela.", "danger")
                    return redirect(url_for(rota_segura_por_perfil[3]))
                return func(*args, **kwargs)

            # ================= PERFIL INVÁLIDO =================
            flash("Perfil de usuário inválido.", "danger")
            return redirect(url_for("usuarios.login"))

        return wrapper
    return decorator