import psycopg2
import psycopg2.extras
from flask import current_app


class DictConnection:
    """
    Wrapper que imita o comportamento do mysql.connector:
    - Suporta uso como context manager (with get_db() as db)
    - cursor(dictionary=True) retorna RealDictCursor (linhas como dict)
    - cursor() sem argumento retorna cursor padrão
    - Faz commit automático ao sair do bloco with sem erros
    - Faz rollback automático em caso de exceção
    """

    def __init__(self, conn):
        self._conn = conn

    def cursor(self, dictionary=False):
        if dictionary:
            return self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        return self._conn.cursor()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()
        return False


def get_db():
    """
    Retorna uma conexão com o PostgreSQL.
    Uso idêntico ao mysql.connector:

        with get_db() as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM usuarios WHERE id = %s", (uid,))
                row = cursor.fetchone()
    """
    conn = psycopg2.connect(current_app.config["DATABASE_URL"])
    return DictConnection(conn)