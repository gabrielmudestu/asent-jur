from flask import render_template, request, flash, redirect, url_for, current_app, Blueprint
from app.services.auth_service import AuthService
from app.services.token_service import TokenService

auth_password_bp = Blueprint("auth_password", __name__)

@auth_password_bp.route('/recuperar-senha', methods=['GET', 'POST'])
def recuperar_senha():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            flash('Por favor, informe seu e-mail cadastrado.', 'danger')
            return render_template('recuperar_senha.html')
        
        try:
            AuthService.solicitar_recuperacao_senha(email)

            flash('Se o e-mail existir, enviaremos instruções para recuperação.', 'info')

            return redirect(url_for('auth_login.login'))
            
        except Exception as e:
            current_app.logger.error(f"Erro na recuperação de senha: {str(e)}")
            flash('Erro ao processar a solicitação. Tente novamente mais tarde.', 'danger')

    # Se for GET, só mostra o formulário
    return render_template('recuperar_senha.html')

@auth_password_bp.route('/redefinir_senha/<token>', methods=['GET', 'POST'])
def redefinir_senha(token):
    try:
        data = TokenService.validar_token_recuperacao(token)
        user_id = data['user_id']
    except Exception as e:
        flash('Link inválido ou expirado.', 'danger')
        return redirect(url_for('auth_login.login'))

    if request.method == 'POST':
        senha = request.form.get('senha', '').strip()
        confirmar = request.form.get('confirmar', '').strip()
        
        try:
            AuthService.redefinir_senha(user_id, senha, confirmar)

            flash('Senha redefinida com sucesso!', 'success')
            return redirect(url_for('auth_login.login'))
        
        except ValueError as e:
            flash(str(e), 'danger')

        except Exception as e:
            current_app.logger.error(f"Erro ao redefinir senha: {str(e)}")
            flash('Erro interno. Contate o administrador.', 'danger')
    
    return render_template('redefinir_senha.html', token=token)