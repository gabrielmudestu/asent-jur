import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")

    # PostgreSQL — a variável DATABASE_URL é injetada automaticamente pelo Render
    DATABASE_URL = os.getenv("DATABASE_URL")

    # Configurações de e-mail (inalteradas)
    SMTP_SERVER = 'smtp.gmail.com'
    SMTP_PORT = 587
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASS = os.getenv("SMTP_PASS")

    SESSION_COOKIE_SECURE = True  # Sempre True em produção com HTTPS