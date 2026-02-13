from flask import render_template, request, flash, redirect, url_for, current_app, Blueprint
from app.services.auth_service import AuthService

auth_user_bp = Blueprint("auth_user", __name__)

@auth_user_bp.route('/registrar-usuario', methods=['GET', 'POST'])
def registrar_usuario():
    if request.method == 'POST':
        try:
            AuthService.registrar_usuario(request.form)
            
            flash('Usuário registrado com sucesso!', 'success')
            return redirect(url_for('auth_login.login'))

        except ValueError as e:
            flash(str(e), 'danger')

        except Exception as e:
            current_app.logger.error(f"Erro ao registrar usuário: {str(e)}")
            flash('Erro interno. Contate o administrador.', 'danger')

    return render_template('registrar_usuario.html')