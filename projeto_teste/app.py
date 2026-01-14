from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
import pandas as pd
import os
import csv
import mysql.connector
from datetime import datetime
from io import BytesIO

# Importações para o PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageTemplate, Frame
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_codego_2026'

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
db_config = {
    'host': 'localhost',
    'port': 3306,
    'user': 'max',
    'password': 'Joaolopes05',
    'database': 'codego_db'
}

OUTPUT_CSV = 'dados_salvos.csv'

# Lista completa de colunas para o CSV
COLUNAS = [
    'MUNICIPIO ID', 'MUNICIPIO', 'DISTRITO', 'EMPRESA', 'CNPJ', 
    'PROCESSO SEI', 'STATUS DE ASSENTAMENTO', 'OBSERVAÇÕES', 
    'RAMO DE ATIVIDADE', 'EMPREGOS GERADOS', 'OBSERVAÇÕES_1', 
    'QUADRA', 'MÓDULO(S)', 'QTD. MÓDULOS', 'TAMANHO(M²)', 
    'MATRÍCULA(S)', 'OBSEVAÇÕES', 'DATA ESCRITURAÇÃO', 
    'DATA CONTRATO DE COMPRA E VENDA', 'AÇÃO JUDICIAL', 
    'TAXA E OCUPAÇÃO DO IMÓVEL(%)', 'IMÓVEL REGULAR/IRREGULAR', 
    'IRREGULARIDADES?', 'ÚLTIMA VISTORIA', 'OBSERVAÇÕES_2', 
    'ATUALIZADO', 'OBSERVAÇÕES_3', 'PROCESSO JUDICIAL', 
    'STATUS', 'ASSUNTO JUDICIAL'
]

# --- FUNÇÕES DE APOIO ---

def ler_csv_seguro():
    if not os.path.exists(OUTPUT_CSV):
        df = pd.DataFrame(columns=COLUNAS + ['USUARIO_REGISTRO', 'DATA_REGISTRO'])
        df.to_csv(OUTPUT_CSV, index=False, sep=';', encoding='utf-8-sig')
        return df
    try:
        return pd.read_csv(OUTPUT_CSV, sep=';', encoding='utf-8-sig', engine='python', on_bad_lines='skip')
    except Exception as e:
        print(f"Erro ao ler CSV: {e}")
        return pd.DataFrame(columns=COLUNAS)

# --- ROTAS DE NAVEGAÇÃO E ACESSO ---

@app.route('/')
def index():
    if 'role' in session:
        return redirect(url_for('menu' if session['role'] == 'admin' else 'menu_jur'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        session.clear()
        if username == 'admin' and password == '12345':
            session['username'], session['role'] = 'Administrador', 'admin'
            return redirect(url_for('menu'))
        elif username == 'jur' and password == '12345':
            session['username'], session['role'] = 'Setor Jurídico', 'jur'
            return redirect(url_for('menu_jur'))
        else:
            flash('Usuário ou senha incorretos!', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- SUPORTE PARA LINKS ---
@app.route('/recuperar_senha')
def recuperar_senha(): return "Página de recuperação em desenvolvimento."

@app.route('/registrar_usuario')
def registrar_usuario(): return "Página de registro em desenvolvimento."

# --- MENUS ---

@app.route('/menu')
def menu():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    return render_template('menu.html')

@app.route('/menu_jur')
def menu_jur():
    if session.get('role') != 'jur': return redirect(url_for('login'))
    return render_template('menu_jur.html')

# --- ROTAS DE CADASTRO (AQUI ESTÁ A CORREÇÃO) ---

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    """Rota para o Administrador cadastrar novos registros."""
    if session.get('role') != 'admin': return redirect(url_for('login'))
    
    if request.method == 'POST':
        df = ler_csv_seguro()
        novo_registro = {col: request.form.get(col, '') for col in COLUNAS}
        novo_registro['USUARIO_REGISTRO'] = session.get('username')
        novo_registro['DATA_REGISTRO'] = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        df = pd.concat([df, pd.DataFrame([novo_registro])], ignore_index=True)
        df.to_csv(OUTPUT_CSV, index=False, sep=';', encoding='utf-8-sig')
        flash('Cadastro realizado com sucesso!', 'success')
        return redirect(url_for('cadastro'))
        
    return render_template('cadastro.html', colunas=COLUNAS)

@app.route('/cadastro_jur', methods=['GET', 'POST'])
def cadastro_jur():
    """Rota para o Jurídico cadastrar informações judiciais."""
    if session.get('role') != 'jur': return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Lógica de salvar específica do jurídico aqui
        flash('Informação jurídica registrada!', 'success')
        return redirect(url_for('menu_jur'))
        
    return render_template('cadastro_jur.html')

# --- EDIÇÃO ---

@app.route('/selecionar_edicao')
def selecionar_edicao():
    if 'role' not in session: return redirect(url_for('login'))
    df = ler_csv_seguro()
    dados = df.reset_index().rename(columns={'index': 'row_id'}).fillna('').to_dict(orient='records')
    return render_template('selecionar_edicao.html', dados=dados, role=session.get('role'))

@app.route('/editar/<int:row_id>', methods=['GET', 'POST'])
def editar(row_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    df = ler_csv_seguro()
    
    if request.method == 'POST':
        for col in COLUNAS:
            if col in request.form:
                df.at[row_id, col] = request.form.get(col)
        df.to_csv(OUTPUT_CSV, index=False, sep=';', encoding='utf-8-sig')
        flash('Registro atualizado!', 'success')
        return redirect(url_for('selecionar_edicao'))
    
    dados_linha = df.iloc[row_id].to_dict()
    return render_template('editar.html', dados=dados_linha, row_id=row_id, colunas=COLUNAS)

@app.route('/editar_jur/<int:row_id>', methods=['GET', 'POST'])
def editar_jur(row_id):
    if session.get('role') != 'jur': return redirect(url_for('login'))
    df = ler_csv_seguro()
    
    if request.method == 'POST':
        df.at[row_id, 'PROCESSO JUDICIAL'] = request.form.get('PROCESSO JUDICIAL')
        df.at[row_id, 'STATUS'] = request.form.get('STATUS')
        df.at[row_id, 'ASSUNTO JUDICIAL'] = request.form.get('ASSUNTO JUDICIAL')
        df.to_csv(OUTPUT_CSV, index=False, sep=';', encoding='utf-8-sig')
        flash('Dados jurídicos salvos!', 'success')
        return redirect(url_for('selecionar_edicao'))
    
    dados_linha = df.iloc[row_id].to_dict()
    return render_template('editar_jur.html', dados=dados_linha, row_id=row_id)

# --- RELATÓRIOS ---

@app.route('/relatorio', methods=['GET', 'POST'])
def relatorios():
    if 'role' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST':
        empresa_id = request.form.get('empresa')
        return f"Processando PDF para ID {empresa_id}..."

    empresas = []
    try:
        with mysql.connector.connect(**db_config) as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT id, empresa FROM municipal_lots ORDER BY empresa")
                empresas = cursor.fetchall()
    except: pass

    template = 'relatorios_jur.html' if session.get('role') == 'jur' else 'relatorios.html'
    return render_template(template, empresas=empresas)

if __name__ == '__main__':
    app.run(debug=True)