from flask import url_for, redirect
from app.db import get_db
from app.extensions import bcrypt
from app.services.email_service import enviar_email
from app.services.token_service import TokenService

class AuthService:

    @staticmethod
    def autenticar(username, password):
        with get_db() as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT * FROM usuarios WHERE login = %s",
                    (username,)
                )
                usuario = cursor.fetchone()

        if usuario and bcrypt.check_password_hash(usuario['senha'], password):
            return usuario
        
        return None

    @staticmethod
    def solicitar_recuperacao_senha(email):
        with get_db() as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT id, login, email FROM usuarios WHERE email = %s", (email,))
                user = cursor.fetchone()
        
        if not user:
            return True
        
        token = TokenService.gerar_token_recuperacao(user['id'])

        reset_url = url_for('auth_password.redefinir_senha', token=token, _external=True)

        assunto = "Recuperação de senha - CODEGO"

        corpo = f"""
Olá {user['login']},

Você solicitou a recuperação de sua senha no sistema CODEGO.

Para redefinir sua senha, clique no link abaixo:

{reset_url}

Este link é válido por 15 minutos apenas.

Se você não solicitou, ignore este e-mail.

Atenciosamente,
Equipe CODEGO
"""

        return enviar_email(destinatario=user['email'], assunto=assunto, corpo=corpo)
    
    @staticmethod
    def registrar_usuario(form):

        nome = form.get('nome')
        login = form.get('login')
        email = form.get('email')
        senha = form.get('senha')
        departamento = form.get('departamento', '')

        # ====================
        # validação
        # ====================

        if not nome or not login or not email or not senha:
            raise ValueError('Todos os campos obrigatórios devem ser preenchidos.')

        # ====================
        # hash de senha
        # ====================

        senha_hash = bcrypt.generate_password_hash(senha).decode('utf-8')

        # ====================
        # acesso ao banco
        # ====================

        with get_db() as db:
            with db.cursor() as cursor:

                cursor.execute("""
                    INSERT INTO usuarios (nome, login, email, senha, departamento)
                    VALUES (%s, %s, %s, %s, %s)
                """, (nome, login, email, senha_hash, departamento))

                db.commit()

    @staticmethod
    def redefinir_senha(user_id, senha, confirmar):
        if not senha or not confirmar:
            raise ValueError('As senhas não podem ser vazias.')
        
        if senha != confirmar:
            raise ValueError('As senhas não conferem.')
        
        senha_hash = bcrypt.generate_password_hash(senha).decode('utf-8')

        with get_db() as db:
            with db.cursor() as cursor:
                cursor.execute("UPDATE usuarios SET senha = %s WHERE id = %s", (senha_hash, user_id))
                db.commit()

    @staticmethod
    def criar_sessao(usuario, session):

        ROLE_MAP = {
            "Jurídico": "jur",
            "Assentamento": "assent",
            "admin": "admin"
        }

        session['username'] = usuario['login']
        session['role'] = ROLE_MAP.get(usuario['departamento'], 'user')

    @staticmethod
    def redirect_por_role(role):
        if role == 'jur':
            return redirect(url_for('dashboard.menu_jur'))
        return redirect(url_for('dashboard.menu'))
