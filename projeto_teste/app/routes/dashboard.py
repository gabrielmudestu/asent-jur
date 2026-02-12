from flask import Blueprint, render_template, session, redirect, url_for
from app.utils.decorators import role_required

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route('/menu')
@role_required('assent', 'admin')
def menu():
    return render_template('menu.html')

@dashboard_bp.route('/menu_jur')
@role_required('jur', 'admin')
def menu_jur():
    return render_template('menu_jur.html')