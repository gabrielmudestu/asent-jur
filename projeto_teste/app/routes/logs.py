from flask import Blueprint, render_template, request
from app.db import get_db
from app.utils.decorators import role_required

logs_bp = Blueprint("logs", __name__)

@logs_bp.route('/logs')
@role_required('admin')
def logs():
    logs_data = []
    usernames = []
    username_filter = (request.args.get('username') or '').strip()
    data_inicial = (request.args.get('data_inicial') or '').strip()
    data_final = (request.args.get('data_final') or '').strip()

    try:
        with get_db() as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("""
                    SELECT DISTINCT username
                    FROM logs
                    WHERE username IS NOT NULL AND username != ''
                    ORDER BY username
                """)
                usernames = [row['username'] for row in cursor.fetchall()]

                query = """
                    SELECT user_id, username, action, descricao, timestamp
                    FROM logs
                    WHERE 1=1
                """
                params = []

                if username_filter:
                    query += " AND username = %s"
                    params.append(username_filter)

                if data_inicial:
                    query += " AND DATE(timestamp) >= %s"
                    params.append(data_inicial)

                if data_final:
                    query += " AND DATE(timestamp) <= %s"
                    params.append(data_final)

                query += " ORDER BY timestamp DESC LIMIT 1000"
                cursor.execute(query, tuple(params))
                logs_data = cursor.fetchall()
    except Exception as err:
        print(f"Erro logs: {err}")
    return render_template(
        'logs.html',
        logs=logs_data,
        usernames=usernames,
        username_filter=username_filter,
        data_inicial=data_inicial,
        data_final=data_final,
    )
