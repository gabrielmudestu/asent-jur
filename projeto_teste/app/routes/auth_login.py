from flask import render_template, request, flash, redirect, url_for, session, current_app, Blueprint
from app.services.auth_service import AuthService

auth_login_bp = Blueprint("auth_login", __name__)

@auth_login_bp.route("/")
def index():
    return render_template("login.html")

@auth_login_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password', '').strip()

        try:
            usuario = AuthService.autenticar(username, password)
            if usuario:
                AuthService.criar_sessao(usuario, session)
                return AuthService.redirect_por_role(session['role'])

                
            flash('Usuário ou senha inválidos!', 'danger')
        except Exception as e:
            current_app.logger.error(str(e))
            flash('Erro interno. Contate o administrador.', 'danger')

    return render_template('login.html')

@auth_login_bp.route("/logout")
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for("auth_login.login"))