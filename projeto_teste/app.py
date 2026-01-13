from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
import pandas as pd
import os
import csv
import mysql.connector
from datetime import datetime
from io import BytesIO

# Importações para o PDF (ReportLab)
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageTemplate, Frame
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

# Configuração de Logs
try:
    from logger_config import sistema_logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    sistema_logger = logging.getLogger('sistema')

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
db_config = {
    'host': 'localhost',
    'port': 3306,
    'user': 'max',
    'password': 'Joaolopes05',
    'database': 'codego_db'
}

# --- CONFIGURAÇÃO DE DADOS (CSV) ---
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

OUTPUT_CSV = 'dados_salvos.csv'

# --- FUNÇÕES AUXILIARES ---

def add_watermark(canvas, doc):
    """Marca d'água com PNG (melhor qualidade)."""
    canvas.saveState()
    
    logo_path = 'logo_codego.png'  # ou o nome exato do seu arquivo PNG
    if os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        
        # Dimensões da página A4
        page_width = A4[0]  # 595.28 pontos
        page_height = A4[1]  # 841.89 pontos
        
        # Tamanho da marca d'água (PNG mantém proporção e qualidade)
        width = 600
        height = 150
        
        # Centro da página
        center_x = page_width / 2
        center_y = page_height / 2
        
        # Posiciona no centro SEM rotação (PNG fica perfeito)
        canvas.translate(center_x, center_y)
        
        canvas.rotate(45)  # Sem rotação para PNG
        # Opacidade para PNG (transparência nativa + alpha adicional)
        canvas.setFillAlpha(0.12)  # 12% de opacidade
        
        # Desenha a imagem PNG (qualidade máxima)
        canvas.drawImage(
            logo,
            -width/2,
            -height/2,
            width=width,
            height=height,
            mask='auto'  # Usa transparência nativa do PNG
        )
        
        canvas.setFillAlpha(1.0)
    
    canvas.restoreState()



def ler_csv_seguro():
    if not os.path.exists(OUTPUT_CSV):
        df_init = pd.DataFrame(columns=COLUNAS + ['USUARIO_REGISTRO', 'DATA_REGISTRO'])
        df_init.to_csv(OUTPUT_CSV, index=False, sep=';', encoding='utf-8')
        return df_init
    try:
        return pd.read_csv(OUTPUT_CSV, sep=';', on_bad_lines='skip', encoding='utf-8', engine='python')
    except Exception as e:
        sistema_logger.error(f"Erro ao ler CSV: {e}")
        return pd.DataFrame(columns=COLUNAS)

def salvar_no_csv(dados_dict):
    dados_dict['USUARIO_REGISTRO'] = session.get('username', 'sistema')
    dados_dict['DATA_REGISTRO'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    colunas_completas = COLUNAS + ['USUARIO_REGISTRO', 'DATA_REGISTRO']
    novo_df = pd.DataFrame([dados_dict])
    novo_df = novo_df.reindex(columns=colunas_completas, fill_value='')
    header = not os.path.exists(OUTPUT_CSV)
    novo_df.to_csv(OUTPUT_CSV, mode='a', index=False, header=header, 
                   encoding='utf-8', sep=';', quoting=csv.QUOTE_MINIMAL)

# --- MIDDLEWARE DE SEGURANÇA ---

@app.before_request
def before_request_func():
    caminhos_livres = ['login', 'static', 'recuperar_senha', 'registrar_usuario']
    if 'username' not in session and request.endpoint not in caminhos_livres:
        return redirect(url_for('login'))

# --- ROTAS DE AUTENTICAÇÃO ---

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('menu_jur' if session.get('role') == 'jur' else 'menu'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == '12345':
            session['username'], session['role'] = username, 'admin'
            return redirect(url_for('menu'))
        elif username == 'jur' and password == '12345':
            session['username'], session['role'] = username, 'jur'
            return redirect(url_for('menu_jur'))
        else:
            flash('Usuário ou senha inválidos!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Sessão encerrada.', 'info')
    return redirect(url_for('login'))

# --- ROTAS DE MENU ---

@app.route('/menu')
def menu():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    return render_template('menu.html')

@app.route('/menu_jur')
def menu_jur():
    if session.get('role') != 'jur': return redirect(url_for('login'))
    return render_template('menu_jur.html')

# --- ROTAS DE CADASTRO ---

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    if request.method == 'POST':
        dados = {col: request.form.get(col, '') for col in COLUNAS}
        salvar_no_csv(dados)
        flash('Cadastro realizado!', 'success')
        return redirect(url_for('cadastro'))
    return render_template('cadastro.html', colunas=COLUNAS, username=session.get('username'))

@app.route('/cadastro_jur', methods=['GET', 'POST'])
def cadastro_jur():
    if session.get('role') != 'jur': return redirect(url_for('login'))
    if request.method == 'POST':
        dados = {col: '' for col in COLUNAS}
        dados['PROCESSO JUDICIAL'] = request.form.get('processo_judicial', '')
        dados['STATUS'] = request.form.get('status', '')
        dados['ASSUNTO JUDICIAL'] = request.form.get('assunto_judicial', '')
        salvar_no_csv(dados)
        flash('Registro jurídico salvo!', 'success')
        return redirect(url_for('menu_jur'))
    return render_template('cadastro_jur.html', username=session.get('username'))

# --- ROTAS DE EDIÇÃO ---

@app.route('/selecionar_edicao')
def selecionar_edicao():
    try:
        with mysql.connector.connect(**db_config) as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT MUNICIPIO, EMPRESA, CNPJ FROM municipal_lots")
                dados = cursor.fetchall()
    except mysql.connector.Error as err:
        dados = []
        print(f"Erro ao buscar dados: {err}")

    return render_template('selecionar_edicao.html', dados=dados, role=session.get('role'))

@app.route('/editar/<int:row_id>', methods=['GET', 'POST'])
def editar(row_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    df = ler_csv_seguro()
    if request.method == 'POST':
        for col in COLUNAS[:-3]:
            df.at[row_id, col] = request.form.get(col, '')
        df.to_csv(OUTPUT_CSV, index=False, sep=';', quoting=csv.QUOTE_MINIMAL, encoding='utf-8')
        flash('Alterações salvas!', 'success')
        return redirect(url_for('selecionar_edicao'))
    dados_linha = df.iloc[row_id].to_dict()
    return render_template('editar.html', dados=dados_linha, colunas=COLUNAS[:-3], row_id=row_id)

@app.route('/editar_jur/<int:row_id>', methods=['GET', 'POST'])
def editar_jur(row_id):
    if session.get('role') != 'jur': return redirect(url_for('login'))
    df = ler_csv_seguro()
    if request.method == 'POST':
        df.at[row_id, 'PROCESSO JUDICIAL'] = request.form.get('PROCESSO JUDICIAL', '')
        df.at[row_id, 'STATUS'] = request.form.get('STATUS', '')
        df.at[row_id, 'ASSUNTO JUDICIAL'] = request.form.get('ASSUNTO JUDICIAL', '')
        df.to_csv(OUTPUT_CSV, index=False, sep=';', quoting=csv.QUOTE_MINIMAL, encoding='utf-8')
        flash('Dados jurídicos atualizados!', 'success')
        return redirect(url_for('menu_jur'))
    dados_linha = df.iloc[row_id].to_dict()
    return render_template('editar_jur.html', dados=dados_linha, colunas_fixas=COLUNAS[:-3], colunas_editaveis=COLUNAS[-3:], row_id=row_id)

# --- ROTA DE RELATÓRIOS ---

@app.route('/relatorio', methods=['GET', 'POST'])
def relatorios():
    if request.method == 'POST':
        empresa_id = request.form.get('empresa')
        if not empresa_id:
            flash("Selecione uma empresa.", "warning")
            return redirect(url_for('relatorios'))
        try:
            with mysql.connector.connect(**db_config) as db:
                with db.cursor(dictionary=True) as cursor:
                    cursor.execute("SELECT * FROM municipal_lots WHERE id = %s", (int(empresa_id),))
                    lot = cursor.fetchone()
            if not lot: return "Empresa não encontrada.", 404

            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
            template = PageTemplate(id='watermark', frames=[frame], onPage=add_watermark)
            doc.addPageTemplates([template])
            styles = getSampleStyleSheet()
            story = []
            title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, spaceAfter=20)
            story.append(Paragraph(f"Relatório: {lot.get('empresa', 'N/A')}", title_style))
            story.append(Spacer(1, 12))
            
            data = [["Campo", "Valor"]]
            for k, v in lot.items(): data.append([str(k).replace('_', ' ').upper(), str(v if v else '-')])
            
            table = Table(data, colWidths=[150, 350])
            table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1a233a')), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('GRID', (0,0), (-1,-1), 0.5, colors.grey)]))
            story.append(table)
            doc.build(story)
            buffer.seek(0)
            response = make_response(buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename="relatorio_{empresa_id}.pdf"'
            return response
        except Exception as e: return f"Erro PDF: {e}"

    empresas = []
    try:
        with mysql.connector.connect(**db_config) as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT id, empresa FROM municipal_lots")
                empresas = cursor.fetchall()
    except: pass
    return render_template('relatorios.html', empresas=empresas, datetime=datetime)


# --- OUTRAS ROTAS ---

@app.route('/registrar-usuario', methods=['GET', 'POST'])
def registrar_usuario():
    if request.method == 'POST':
        flash('Solicitação enviada!', 'success')
        return redirect(url_for('login'))
    return render_template('registrar_usuario.html')

@app.route('/recuperar-senha', methods=['GET', 'POST'])
def recuperar_senha():
    if request.method == 'POST':
        flash('E-mail de recuperação enviado!', 'success')
        return redirect(url_for('login'))
    return render_template('recuperar_senha.html')

@app.route('/teste-conexao')
def teste_conexao():
    try:
        with mysql.connector.connect(**db_config) as db:
            with db.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()  # Consome o resultado
                return f"Conexão com o banco OK! Resultado: {result}"
    except Exception as e:
        return f"Erro: {e}"

@app.route('/logs')
def logs():
    if 'username' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    logs_data = []
    try:
        with mysql.connector.connect(**db_config) as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM logs ORDER BY timestamp DESC")
                logs_data = cursor.fetchall()
    except mysql.connector.Error as err:
        print(f"Erro logs: {err}")
    return render_template('logs.html', logs=logs_data)

if __name__ == '__main__':
    ler_csv_seguro()
    app.run(host='0.0.0.0', port=5000, debug=True)