from functools import wraps
from flask import session, redirect, url_for, flash

def role_required(*roles_permitidas):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):

            # não logado
            if 'username' not in session:
                flash('Faça login primeiro.', 'warning')
                return redirect(url_for('auth_login.login'))

            role_usuario = session.get('role')

            # sem permissão
            if role_usuario not in roles_permitidas:
                flash('Você não tem permissão para acessar esta página.', 'danger')
                return redirect(url_for('dashboard.menu'))

            return func(*args, **kwargs)

        return wrapper
    return decorator
