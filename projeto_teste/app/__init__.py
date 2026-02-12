from flask import Flask, session, redirect, url_for, request
from itsdangerous import URLSafeTimedSerializer
from dotenv import load_dotenv
from app.extensions import bcrypt

def create_app():
    app = Flask(__name__)
    app.config.from_object("app.config.Config")

    load_dotenv()
    bcrypt.init_app(app)

    # registrar blueprints
    from app.routes.auth import auth_bp
    from app.routes.cadastro import cadastro_bp
    from app.routes.relatorios import relatorio_bp
    from app.routes.logs import logs_bp
    from app.routes.edicao import edicao_bp
    from app.routes.juridico import juridico_bp
    from app.routes.dashboard import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(cadastro_bp)
    app.register_blueprint(relatorio_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(edicao_bp)
    app.register_blueprint(juridico_bp)

    return app
