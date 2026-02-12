from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from app.services.token_service import TokenService
from app.services.auth_service import AuthService

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/")
def index():
    return render_template("login.html")

@auth_bp.route('/login', methods=['GET', 'POST'])
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

@auth_bp.route("/logout")
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for("auth.login"))


@auth_bp.route('/recuperar-senha', methods=['GET', 'POST'])
def recuperar_senha():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            flash('Por favor, informe seu e-mail cadastrado.', 'danger')
            return render_template('recuperar_senha.html')
        
        try:
            AuthService.solicitar_recuperacao_senha(email)

            flash('Se o e-mail existir, enviaremos instruções para recuperação.', 'info')

            return redirect(url_for('auth.login'))
            
        except Exception as e:
            current_app.logger.error(f"Erro na recuperação de senha: {str(e)}")
            flash('Erro ao processar a solicitação. Tente novamente mais tarde.', 'danger')

    # Se for GET, só mostra o formulário
    return render_template('recuperar_senha.html')

@auth_bp.route('/registrar-usuario', methods=['GET', 'POST'])
def registrar_usuario():
    if request.method == 'POST':
        try:
            AuthService.registrar_usuario(request.form)
            
            flash('Usuário registrado com sucesso!', 'success')
            return redirect(url_for('auth.login'))

        except ValueError as e:
            flash(str(e), 'danger')

        except Exception as e:
            current_app.logger.error(f"Erro ao registrar usuário: {str(e)}")
            flash('Erro interno. Contate o administrador.', 'danger')

    return render_template('registrar_usuario.html')

@auth_bp.route('/redefinir_senha/<token>', methods=['GET', 'POST'])
def redefinir_senha(token):
    try:
        data = TokenService.validar_token_recuperacao(token)
        user_id = data['user_id']
    except Exception as e:
        flash('Link inválido ou expirado.', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        senha = request.form.get('senha', '').strip()
        confirmar = request.form.get('confirmar', '').strip()
        
        try:
            AuthService.redefinir_senha(user_id, senha, confirmar)

            flash('Senha redefinida com sucesso!', 'success')
            return redirect(url_for('auth.login'))
        
        except ValueError as e:
            flash(str(e), 'danger')

        except Exception as e:
            current_app.logger.error(f"Erro ao redefinir senha: {str(e)}")
            flash('Erro interno. Contate o administrador.', 'danger')
    
    return render_template('redefinir_senha.html', token=token)