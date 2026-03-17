from flask import render_template, request, flash, redirect, session, url_for, current_app, Blueprint
from app.services.auth_service import AuthService
from app.utils.decorators import role_required

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

@auth_user_bp.route('/registrar-colaborador')
@role_required('assent_gestor', 'jur_gestor', 'admin') # Garantindo que só gestores acessem
def registrar_colaborador():
    role = session.get('role')
    
    # Define o departamento automático baseado na role do gestor
    if role == 'jur_gestor':
        depto_predefinido = "Usuário - Jurídico"
    elif role == 'assent_gestor':
        depto_predefinido = "Usuário - Assentamento"
    else:
        # Se for admin acessando por aqui, podemos deixar um padrão ou redirecionar
        depto_predefinido = "Administrador"
        
    return render_template('registrar_colaborador.html', depto=depto_predefinido)