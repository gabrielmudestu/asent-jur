from flask import Blueprint, render_template, session, redirect, url_for
from app.db import get_db
from app.utils.decorators import role_required

logs_bp = Blueprint("logs", __name__)

@logs_bp.route('/logs')
@role_required('admin')
def logs():
    logs_data = []
    try:
        with get_db() as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT user_id, username, action, descricao, timestamp FROM logs ORDER BY timestamp DESC LIMIT 1000")
                logs_data = cursor.fetchall()
    except Exception as err:
        print(f"Erro logs: {err}")
    return render_template('logs.html', logs=logs_data)