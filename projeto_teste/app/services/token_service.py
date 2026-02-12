from itsdangerous import URLSafeTimedSerializer
from flask import current_app

class TokenService:

    @staticmethod
    def gerar_token_recuperacao(user_id):
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return serializer.dumps({'user_id': user_id}, salt='recover')

    @staticmethod
    def validar_token_recuperacao(token, max_age=900):
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return serializer.loads(token, salt='recover', max_age=max_age)
