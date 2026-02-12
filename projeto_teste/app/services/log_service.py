from flask import session
from app.db import get_db

def gravar_log(acao, descricao='', usuario_id=None, usuario_username=None, db_conn=None):
    """Grava um log na tabela logs com user_id, username e action."""
    if db_conn is None:
        db = get_db()
    else:
        db = db_conn

    # Se não for passado user_id/username, usa os da sessão
    user_id = usuario_id or session.get('user_id')
    username = usuario_username or session.get('username')

    with db.cursor() as cursor:
        cursor.execute("""
            INSERT INTO logs (user_id, username, action, descricao)
            VALUES (%s, %s, %s, %s)
        """, (user_id, username, acao, descricao[:500]))
        db.commit()

    # Só fecha se não foi passada conexão externa
    if not db_conn and db:
        db.close()
