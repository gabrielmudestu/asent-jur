from flask import Blueprint, render_template, session, redirect, url_for
from app.utils.decorators import role_required

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route('/menu/<modo>')
@role_required('assent', 'jur', 'admin','assent_gestor','jur_gestor')
def menu(modo):
    
    if modo == "jur":
        return render_template('menu_jur.html')
    
    return render_template('menu.html')