from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
import pandas as pd
import os
import csv
import mysql.connector
from datetime import datetime
from io import BytesIO

# Importações para o PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = Flask(__name__)
app.secret_key = 'chave_mestra_codego'

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Joaolopes05',
    'database': 'codego_db'
}

# --- CONFIGURAÇÃO DE DADOS (CSV) ---
COLUNAS = [
    'MUNICIPIO ID', 'MUNICIPIO', 'DISTRITO', 'EMPRESA', 'CNPJ', 
    'PROCESSO SEI', 'STATUS DE ASSENTAMENTO', 'OBSERVAÇÕES', 
    'RAMO DE ATIVIDADE', 'EMPREGOS GERADOS', 'QUADRA', 'MÓDULO(S)', 
    'PROCESSO JUDICIAL', 'STATUS', 'ASSUNTO JUDICIAL'
]
OUTPUT_CSV = 'dados_salvos.csv'

def ler_csv_seguro():
    if not os.path.exists(OUTPUT_CSV):
        df = pd.DataFrame(columns=COLUNAS)
        df.to_csv(OUTPUT_CSV, index=False, sep=';', encoding='utf-8')
        return df
    return pd.read_csv(OUTPUT_CSV, sep=';', encoding='utf-8', engine='python')

# --- AUTENTICAÇÃO ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == 'admin' and password == '12345':
            session['username'] = 'Administrador'
            session['role'] = 'admin'
            return redirect(url_for('menu'))
        elif username == 'jur' and password == '12345':
            session['username'] = 'Setor Jurídico'
            session['role'] = 'jur'
            return redirect(url_for('menu_jur'))
        else:
            flash('Usuário ou senha inválidos!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ROTAS DE NAVEGAÇÃO ---

@app.route('/menu')
def menu():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    return render_template('menu.html')

@app.route('/menu_jur')
def menu_jur():
    if session.get('role') != 'jur': return redirect(url_for('login'))
    return render_template('menu_jur.html')

# --- ROTA DE RELATÓRIOS (Lógica de Template Dinâmico) ---

@app.route('/relatorios', methods=['GET', 'POST'])
def relatorios():
    if 'username' not in session: return redirect(url_for('login'))

    if request.method == 'POST':
        empresa_id = request.form.get('empresa')
        try:
            with mysql.connector.connect(**db_config) as db:
                with db.cursor(dictionary=True) as cursor:
                    cursor.execute("SELECT * FROM municipal_lots WHERE id = %s", (empresa_id,))
                    lot = cursor.fetchone()
            
            # Geração do PDF
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            story = [Paragraph(f"Relatório: {lot['empresa']}", getSampleStyleSheet()['Title'])]
            doc.build(story)
            buffer.seek(0)
            
            response = make_response(buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename="relatorio.pdf"'
            return response
        except Exception as e:
            return f"Erro ao gerar PDF: {e}"

    # Lógica GET: Busca empresas e decide qual HTML renderizar
    empresas = []
    try:
        with mysql.connector.connect(**db_config) as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT id, empresa FROM municipal_lots ORDER BY empresa")
                empresas = cursor.fetchall()
    except: pass

    # AQUI ESTÁ A MÁGICA:
    if session.get('role') == 'jur':
        return render_template('relatorios_jur.html', empresas=empresas)
    else:
        return render_template('relatorios.html', empresas=empresas)

# --- OUTRAS ROTAS ---

@app.route('/cadastro_jur')
def cadastro_jur():
    if session.get('role') != 'jur': return redirect(url_for('login'))
    return render_template('cadastro_jur.html')

@app.route('/selecionar_edicao')
def selecionar_edicao():
    df = ler_csv_seguro()
    return render_template('selecionar_edicao.html', dados=df.to_dict(orient='records'), role=session.get('role'))

if __name__ == '__main__':
    app.run(debug=True)