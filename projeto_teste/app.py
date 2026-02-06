# flask faz ligação com o servidor Web e o inicia
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
import os
import mysql.connector
from datetime import datetime, timedelta
from io import BytesIO

# importações para realização do relatório
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageTemplate, Frame, Image, NextPageTemplate
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
#criptografia da senha para não aparecer em texto branco no mySQL
from flask_bcrypt import Bcrypt

from itsdangerous import URLSafeTimedSerializer
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from itsdangerous import URLSafeTimedSerializer
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY', 'fallback-local-key')
app.config['SECRET_KEY'] = app.secret_key
app.config['FLASK_ENV'] = os.environ.get('FLASK_ENV', 'development')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
bcrypt = Bcrypt(app)

# configurações que permitem o acesso ao BD do mySQL (credenciais de acesso)
db_config = {
    'host': os.environ.get('DB_HOST'),
    'port': int(os.environ.get('DB_PORT')),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASSWORD'),
    'database': os.environ.get('DB_NAME')
}

#  dados como são recebidos no banco de dados 
COLUNAS = [
    'municipio', 'distrito', 'empresa', 'cnpj',
    'processo_sei', 'status_de_assentamento', 'observacoes',
    'ramo_de_atividade', 'empregos_gerados', 'observacoes_1',
    'quadra', 'modulo_s', 'qtd_modulos', 'tamanho_m2',
    'matricula_s', 'obsevacoes', 'data_escrituracao',
    'data_contrato_de_compra_e_venda', 'acao_judicial',
    'taxa_e_ocupacao_do_imovel', 'imovel_regular_irregular',
    'irregularidades', 'ultima_vistoria', 'observacoes_2',
    'atualizado', 'observacoes_3', 'processo_judicial',
    'status', 'assunto_judicial', 'valor_da_causa',
]

# nomes como serão vistos pelos usuários (tradução)
LABELS = {
    'municipio': 'Município',
    'distrito': 'Distrito',
    'empresa': 'Empresa',
    'cnpj': 'CNPJ',
    'processo_sei': 'Processo SEI',
    'status_de_assentamento': 'Status de Assentamento',
    'observacoes': 'Observações',
    'ramo_de_atividade': 'Ramo de Atividade',
    'empregos_gerados': 'Empregos Gerados',
    'observacoes_1': 'Observações 1',
    'quadra': 'Quadra',
    'modulo_s': 'Módulo(s)',
    'qtd_modulos': 'Quantidade de Módulos',
    'tamanho_m2': 'Tamanho (m²)',
    'matricula_s': 'Matrícula(s)',
    'obsevacoes': 'Observações',
    'data_escrituracao': 'Data de Escrituração',
    'data_contrato_de_compra_e_venda': 'Data do Contrato de Compra e Venda',
    'acao_judicial': 'Ação Judicial',
    'taxa_e_ocupacao_do_imovel': 'Taxa e Ocupação do Imóvel (%)',
    'imovel_regular_irregular': 'Imóvel Regular/Irregular',
    'irregularidades': 'Irregularidades',
    'ultima_vistoria': 'Última Vistoria',
    'observacoes_2': 'Observações 2',
    'atualizado': 'Atualizado',
    'observacoes_3': 'Observações 3',
    'processo_judicial': 'Processo Judicial',
    'status': 'Status',
    'assunto_judicial': 'Assunto Judicial',
    'valor_da_causa': 'Valor da Causa',
}

#as fixas delimitam os campos relacionados ao usuários de Assentamento 
chaves_fixas = COLUNAS[:-4] 
#as editáveis indicam os campos referentes aos usuários do Jurídico
chaves_editaveis = COLUNAS[-4:]

labels_fixas = {k: LABELS[k] for k in chaves_fixas}
labels_editaveis = {k: LABELS[k] for k in chaves_editaveis}

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'imagens_empresas')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# função que grava o log na tabela logs do banco de dados
def gravar_log(acao, descricao='', usuario_id=None, usuario_username=None, db_conn=None):
    """Grava um log na tabela logs com user_id, username e action."""
    if db_conn is None:
        db = mysql.connector.connect(**db_config)
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

# função que adiciona a marca d`água no fundo do relatório (inclinada a 45 graus)

def add_watermark(canvas, doc):
    canvas.saveState()
    logo_path = os.path.join(app.root_path, 'static', 'logo_codego_grey.png')
    if os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        page_width, page_height = A4
        iw, ih = logo.getSize()
        scale = 600 / iw
        width = 600
        height = ih * scale

        canvas.translate(page_width / 2, page_height / 2)
        canvas.rotate(45)
        canvas.setFillAlpha(0.08)
        canvas.drawImage(logo, -width/2, -height/2, width=width, height=height, mask='auto')
        canvas.setFillAlpha(1.0)
    canvas.restoreState()

# --- MIDDLEWARE DE SEGURANÇA ---

@app.before_request
def before_request_func():
    caminhos_livres = ['login', 'static', 'recuperar_senha', 'registrar_usuario', 'redefinir_senha']
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

        try:
            with mysql.connector.connect(**db_config) as db:
                with db.cursor(dictionary=True) as cursor:
                    cursor.execute("SELECT * FROM usuarios WHERE login = %s", (username,))
                    usuario = cursor.fetchone()
                    if usuario and bcrypt.check_password_hash(usuario['senha'], password):
                        session['username'] = usuario['login']
                        if usuario['departamento'] == 'Jurídico':
                            session['role'] = 'jur'
                            return redirect(url_for('menu_jur'))
                        elif usuario['departamento'] == 'Assentamento':
                            session['role'] = 'assent'
                            return redirect(url_for('menu'))
                        elif usuario['departamento'] == 'admin':
                            session['role'] = 'admin'
                            return redirect(url_for('menu'))
                    else:
                        flash('Usuário ou senha inválidos!', 'danger')
        except Exception as e:
            flash(f'Erro ao fazer login: {e}', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Sessão encerrada.', 'info')
    return redirect(url_for('login'))

# --- ROTAS DE MENU ---

@app.route('/menu')
def menu():
    if session.get('role') not in ('assent','admin'): return redirect(url_for('login'))
    return render_template('menu.html')

@app.route('/menu_jur')
def menu_jur():
    if session.get('role') != 'jur': return redirect(url_for('login'))
    return render_template('menu_jur.html')

# --- ROTAS DE CADASTRO ---

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if session.get('role') not in ('assent','admin'): return redirect(url_for('login'))
    if request.method == 'POST':
        colunas_map = {
            'MUNICIPIO': 'municipio',
            'DISTRITO': 'distrito',
            'EMPRESA': 'empresa',
            'CNPJ': 'cnpj',
            'PROCESSO SEI': 'processo_sei',
            'STATUS DE ASSENTAMENTO': 'status_de_assentamento',
            'RAMO DE ATIVIDADE': 'ramo_de_atividade',
            'EMPREGOS GERADOS': 'empregos_gerados',
            'QUADRA': 'quadra',
            'MÓDULO(S)': 'modulo_s',
            'QTD. MÓDULOS': 'qtd_modulos',
            'TAMANHO(M²)': 'tamanho_m2',
            'MATRÍCULA(S)': 'matricula_s',
            'OBSEVAÇÕES': 'obsevacoes',
            'DATA ESCRITURAÇÃO': 'data_escrituracao',
            'DATA CONTRATO DE COMPRA E VENDA': 'data_contrato_de_compra_e_venda',
            'IRREGULARIDADES?': 'irregularidades',
            'ÚLTIMA VISTORIA': 'ultima_vistoria',
            'ATUALIZADO': 'atualizado',
            'IMÓVEL REGULAR/IRREGULAR': 'imovel_regular_irregular',
            'TAXA E OCUPAÇÃO DO IMÓVEL(%)': 'taxa_e_ocupacao_do_imovel',
        }

        campos_numericos = ['processo_sei', 'empregos_gerados', 'quadra', 'qtd_modulos', 'tamanho_m2', 'matricula_s', 'taxa_e_ocupacao_do_imovel']

        dados = {}
        for form_name, db_name in colunas_map.items():
            valor = request.form.get(form_name, '')

            if db_name in campos_numericos:
                if valor.isdigit():
                    dados[db_name] = int(valor)
                else:
                    dados[db_name] = '0'
            else:
                dados[db_name] = valor if valor else '-'

        empresa_id = None
            
        try:
            with mysql.connector.connect(**db_config) as db:
                with db.cursor() as cursor:
                    cols = ', '.join(dados.keys())
                    placeholders = ', '.join(['%s'] * len(dados))
                    query = f"INSERT INTO municipal_lots ({cols}) VALUES ({placeholders})"
                    valores = [dados[campo] for campo in dados.keys()]
                    cursor.execute(query, valores)
                    empresa_id = cursor.lastrowid
                    db.commit()
                    gravar_log(
                        acao=f"CADASTRO_EMPRESA (ID {empresa_id})",
                        descricao = " | ".join([f"{campo}: {valor}" for campo, valor in dados.items()]),
                        usuario_username=session.get('username'),
                        db_conn=db
                    )
                if not empresa_id:
                    raise Exception("Erro ao obter ID do cadastro.")
                
                file = request.files.get('IMAGEM_EMPRESA')
                descricao = request.form.get('DESCRICAO_EMPRESA', '') or ' '

                if file and file.filename.strip():
                    nome_original = file.filename
                    nome_base, ext = os.path.splitext(nome_original)
                    ext = ext.lower()

                    if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                        ext = '.jpg'

                    nome_arquivo = f"empresa{empresa_id}{ext}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)

                    file.save(filepath)

                    caminho_imagem = f"/static/imagens_empresas/{nome_arquivo}".replace('\\', '/')

                    with db.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO empresa_infos (empresa_id, descricao, caminho_imagem)
                            VALUES (%s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                                descricao = VALUES(descricao),
                                caminho_imagem = VALUES(caminho_imagem)
                        """, (empresa_id, descricao, caminho_imagem))
                        db.commit()
                        gravar_log(
                            acao=f"UPLOAD_IMAGEM_EMPRESA (empresa{empresa_id})",
                            usuario_username=session.get('username'),
                            db_conn=db
                        )
            flash('Registro salvo com sucesso!', 'success')
            return redirect(url_for('cadastro'))
        except Exception as e:
            flash(f'Erro ao cadastrar: {e}', 'danger')
    return render_template('cadastro.html', username=session.get('username'))

@app.route('/cadastro_jur', methods=['GET', 'POST'])
def cadastro_jur():
    if session.get('role') != 'jur': return redirect(url_for('login'))
    
    if request.method == 'POST':
        empresa_id = request.form.get('empresa_id')
        dados_jur = {
            'processo_judicial': request.form.get('processo_judicial', ''),
            'status': request.form.get('status', ''),
            'assunto_judicial': request.form.get('assunto_judicial', ''),
            'valor_da_causa': request.form.get('valor_da_causa', '')
        }
        
        try:
            with mysql.connector.connect(**db_config) as db:
                with db.cursor() as cursor:
                    set_clause = ", ".join([f"`{k}` = %s" for k in dados_jur.keys()])
                    query = f"UPDATE municipal_lots SET {set_clause} WHERE id = %s"
                    cursor.execute(query, list(dados_jur.values()) + [empresa_id])
                    db.commit()
                    gravar_log(f"CADASTRO_JURIDICO_INICIAL (ID {empresa_id})", db_conn=db)
            flash('Informações jurídicas adicionadas com sucesso!', 'success')
            return redirect(url_for('menu_jur'))
        except Exception as e:
            flash(f'Erro ao salvar: {e}', 'danger')

    # Lógica GET: Busca empresas que não possuem dados jurídicos preenchidos
    empresas_pendentes = []
    try:
        with mysql.connector.connect(**db_config) as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("""
                    SELECT id, empresa, cnpj FROM municipal_lots 
                    WHERE (processo_judicial IS NULL OR processo_judicial = '' OR processo_judicial = '-')
                    AND empresa != '-' ORDER BY empresa
                """)
                empresas_pendentes = cursor.fetchall()
    except Exception as e:
        print(f"Erro ao buscar empresas: {e}")

    return render_template('cadastro_jur.html', empresas=empresas_pendentes, username=session.get('username'))


# --- ROTAS DE EDIÇÃO ---

@app.route('/selecionar_edicao')
def selecionar_edicao():
    try:
        with mysql.connector.connect(**db_config) as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("""
                    SELECT id, municipio, empresa, cnpj 
                    FROM municipal_lots 
                    WHERE empresa != '-'
                    ORDER BY empresa
                """)
                dados = cursor.fetchall()
    except mysql.connector.Error as err:
        dados = []
        print(f"Erro ao buscar dados: {err}")
    return render_template('selecionar_edicao.html', dados=dados, role=session.get('role'))

@app.route('/editar/<int:empresa_id>', methods=['GET', 'POST'])
def editar(empresa_id):
    if session.get('role') not in ('assent','admin'): return redirect(url_for('login'))

    try:
        with mysql.connector.connect(**db_config) as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM municipal_lots WHERE id = %s", (empresa_id,))
                empresa = cursor.fetchone()
                if not empresa:
                    flash('Empresa não encontrada.', 'danger')
                    return redirect(url_for('selecionar_edicao'))
                
                if request.method == 'POST':
                    campos_numericos = [
                        'processo_sei', 'empregos_gerados', 'quadra', 'qtd_modulos',
                        'tamanho_m2', 'matricula_s', 'taxa_e_ocupacao_do_imovel'
                    ]

                    campos = COLUNAS[:-4] # Pega as chaves fixas
                    set_clause = ', '.join([f"`{col}` = %s" for col in campos])
                    query = f"UPDATE municipal_lots SET {set_clause} WHERE id = %s"
                    valores = []
                    alteracoes = []

                    for col in campos:
                        valor_form = request.form.get(col, '').strip()

                        # Determina o valor que vai para o banco
                        if col in campos_numericos:
                            if valor_form.isdigit():
                                valor_final = int(valor_form)
                            else:
                                valor_final = 0
                        else:
                            valor_final = valor_form if valor_form else '-'

                        # Determina o valor antigo do banco, considerando tipo
                        valor_velho_banco = empresa.get(col)
                        if col in campos_numericos:
                            try:
                                valor_velho = int(valor_velho_banco) if valor_velho_banco not in ('', None) else 0
                            except (ValueError, TypeError):
                                valor_velho = 0
                        else:
                            valor_velho = str(valor_velho_banco) if valor_velho_banco not in ('', None) else '-'

                        # Só adiciona ao log se o valor final for diferente do antigo
                        if valor_final != valor_velho:
                            alteracoes.append(f"{LABELS[col]}: '{valor_velho}' → '{valor_final}'")

                        # Adiciona o valor final para o UPDATE
                        valores.append(valor_final)

                    valores.append(empresa_id)
                    cursor.execute(query, valores)
                    db.commit()
                    empresa_nome = empresa['empresa'] or f'empresa {empresa_id}'
                    descricao_log = f"Empresa: {empresa_nome} (ID {empresa_id})"
                    if alteracoes:
                        descricao_log += " | Alterações: " + "; ".join(alteracoes)
                    else:
                        descricao_log += " | Nenhuma alteração realizada."
                    gravar_log(
                        acao=f"EDIÇÃO_EMPRESA",
                        descricao=descricao_log,
                        usuario_username=session.get('username'),
                        db_conn=db
                    )
                    flash('Alterações salvas!', 'success')
                    return redirect(url_for('selecionar_edicao'))
                return render_template('editar.html', dados=empresa, colunas=chaves_fixas, labels=labels_fixas, empresa_id=empresa_id)
    except Exception as e:
        flash(f'Erro ao editar: {e}', 'danger')
        return redirect(url_for('selecionar_edicao'))

@app.route('/editar_jur/<int:empresa_id>', methods=['GET', 'POST'])
def editar_jur(empresa_id):
    if session.get('role') != 'jur': return redirect(url_for('login'))
    try:
        with mysql.connector.connect(**db_config) as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM municipal_lots WHERE id = %s", (empresa_id,))
                empresa = cursor.fetchone()
                if not empresa:
                    flash('Empresa não encontrada.', 'danger')
                    return redirect(url_for('selecionar_edicao'))
                
                if request.method == 'POST':
                    campos = ['processo_judicial', 'status', 'assunto_judicial', 'valor_da_causa']
                    set_clause = ', '.join([f"`{col}` = %s" for col in campos])
                    query = f"UPDATE municipal_lots SET {set_clause} WHERE id = %s"
                    valores = []
                    alteracoes = []

                    for col in campos:
                        valor_novo = request.form.get(col, '').strip()
                        valor_velho = str(empresa.get(col, '') or '').strip()

                        valores.append(valor_novo)

                        if valor_novo != valor_velho:
                            alteracoes.append(f"{LABELS[col]}: '{valor_velho}' → '{valor_novo}'")

                    valores.append(empresa_id)
                    cursor.execute(query, valores)
                    db.commit()
                    empresa_nome = empresa['empresa'] or f'empresa {empresa_id}'
                    descricao_log = f"Empresa: {empresa_nome} (ID {empresa_id})"
                    if alteracoes:
                        descricao_log += " | Alterações Jurídicas: " + "; ".join(alteracoes)
                    else:
                        descricao_log += " | Nenhuma alteração nos campos jurídicos."
                    gravar_log(
                        acao=f"EDIÇÃO_JURIDICA",
                        descricao=descricao_log,
                        usuario_username=session.get('username'),
                        db_conn=db
                    )
                    flash('Dados jurídicos atualizados!', 'success')
                    return redirect(url_for('selecionar_edicao'))
                return render_template('editar_jur.html', dados=empresa, colunas_fixas=chaves_fixas, colunas_editaveis=chaves_editaveis, labels=labels_fixas, labels_editaveis=labels_editaveis, empresa_id=empresa_id)
    except Exception as e:
        flash(f'Erro ao editar jurídico: {e}', 'danger')
        return redirect(url_for('selecionar_edicao'))

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
            from reportlab.lib.units import inch
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            if not hasattr(pdfmetrics, '_fonts'):
                from reportlab.pdfbase import pdfmetrics
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                leftMargin=72,
                rightMargin=72,
                topMargin=120,
                bottomMargin=72
            )

            # Frame onde o conteúdo será desenhado
            frame = Frame(
                doc.leftMargin,
                doc.bottomMargin,
                doc.width,
                doc.height,
                id='normal'
            )

            # Template com marca d’água → será usado em TODAS as páginas
            template = PageTemplate(
                id='watermark_template',
                frames=[frame],
                onPage=add_watermark
            )
            doc.addPageTemplates([template])

            # Estilos
            styles = getSampleStyleSheet()
            font_title = 'Helvetica-Bold'
            font_normal = 'Helvetica'

            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontName=font_title,
                fontSize=16,
                leading=22,
                alignment=1,
                spaceAfter=20,
                textColor=colors.HexColor('#1a233a')
            )

            subtitle_style = ParagraphStyle(
                'Subtitle',
                parent=styles['Normal'],
                fontName=font_title,
                fontSize=12,
                leading=16,
                alignment=1,
                spaceAfter=10,
                textColor=colors.HexColor('#374151')
            )

            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontName=font_normal,
                fontSize=10,
                leading=14,
                spaceBefore=0,
                spaceAfter=0
            )

            cell_style = ParagraphStyle(
                'CellStyle',
                parent=styles['Normal'],
                fontName=font_normal,
                fontSize=9,
                leading=12,
                wordWrap='CJK'
            )

            # Monta story
            story = []

            # Logo no topo
            logo_path = os.path.join(app.root_path, 'static', 'logo_codego.png')
            if os.path.exists(logo_path):
                logo = Image(logo_path, width=300, height=60, hAlign='CENTER')
                story.append(logo)
                story.append(Spacer(1, 20))

            # Título
            story.append(Paragraph("RELATÓRIO DE ASSENTAMENTO", title_style))
            story.append(Paragraph(f"Relatório: {lot.get('empresa', 'N/A')}", title_style))
            story.append(Spacer(1, 12))

            # Tabela
            data = [["Campo", "Valor"]]
            for k, v in lot.items():
                campo = str(k).replace('_', ' ').upper()
                valor = str(v) if v is not None else '-'
                data.append([
                    Paragraph(campo, cell_style),
                    Paragraph(valor, cell_style)
                ])

            table = Table(data, colWidths=[150, 350], repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a233a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), font_title),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),

                ('FONTNAME', (0, 1), (-1, -1), font_normal),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('VALIGN', (0, 1), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                ('LEFTPADDING', (0, 1), (-1, -1), 6),
                ('RIGHTPADDING', (0, 1), (-1, -1), 6),
                ('BACKGROUND', (0, 1), (-1, -1), colors.transparent),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            story.append(table)

            # Rodapé
            footer_para = Paragraph(
                f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Usuário: {session.get('username', 'sistema')}",
                ParagraphStyle(
                    'Footer',
                    parent=styles['Normal'],
                    fontName=font_normal,
                    fontSize=8,
                    alignment=2,
                    spaceBefore=10,
                    textColor=colors.grey
                )
            )
            story.append(Spacer(1, 10))
            story.append(footer_para)

            # Força o mesmo template em todas as páginas
            # (isso é o que faz o watermark aparecer em todas elas)
            story.insert(0, NextPageTemplate('watermark_template'))

            # Gera o PDF
            doc.build(story)

            # Envia o PDF
            buffer.seek(0)
            response = make_response(buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'inline; filename="relatorio_{empresa_id}.pdf"'
            return response
        except Exception as e: return f"Erro PDF: {e}"

    empresas = []
    empresas_info = {}

    try:
        with mysql.connector.connect(**db_config) as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT id, empresa FROM municipal_lots WHERE empresa != '-' ORDER BY empresa")
                empresas = cursor.fetchall()
                cursor.execute("SELECT empresa_id, descricao, caminho_imagem FROM empresa_infos")
                infos = cursor.fetchall()
        for row in infos:
            empresas_info[str(row['empresa_id'])] = {
                "descricao": row.get('descricao') or 'Sem descrição cadastrada.',
                "foto": row.get('caminho_imagem') or 'static/empresa-default.png',
            }
    except mysql.connector.Error as err:
        print("Erro ao carregar dados:", err)
    template = 'relatorios_jur.html' if session.get('role') == 'jur' else 'relatorios.html'
    return render_template(template, empresas=empresas, empresas_info=empresas_info)

# --- OUTRAS ROTAS ---

@app.route('/registrar-usuario', methods=['GET', 'POST'])
def registrar_usuario():
    if request.method == 'POST':
        nome = request.form.get('nome')
        login = request.form.get('login')
        email = request.form.get('email')
        senha = request.form.get('senha')
        departamento = request.form.get('departamento', '')

        senha_hash = bcrypt.generate_password_hash(senha).decode('utf-8')

        # Validação básica
        if not nome or not login or not email or not senha:
            flash('Todos os campos obrigatórios devem ser preenchidos.', 'danger')
            return render_template('registrar_usuario.html')

        try:
            with mysql.connector.connect(**db_config) as db:
                with db.cursor() as cursor:
                    # Supondo que você tenha uma tabela 'usuarios' com os campos abaixo
                    cursor.execute("""
                        INSERT INTO usuarios (nome, login, email, senha, departamento)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (nome, login, email, senha_hash, departamento))
                    db.commit()
                flash('Usuário registrado com sucesso!', 'success')
                return redirect(url_for('login'))
        except Exception as e:
            flash(f'Erro ao registrar usuário: {e}', 'danger')

    return render_template('registrar_usuario.html')

@app.route('/recuperar-senha', methods=['GET', 'POST'])
def recuperar_senha():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            flash('Por favor, informe seu e-mail cadastrado.', 'danger')
            return render_template('recuperar_senha.html')
        
        try:
            # Buscar usuário pelo login
            db = mysql.connector.connect(**db_config)
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT id, login, email FROM usuarios WHERE email = %s", (email,))
            user = cursor.fetchone()
            cursor.close()

            if not user:
                # Mesmo se não existir, mostra a mesma mensagem para segurança
                flash('Se o e-mail for válido, enviaremos instruções de recuperação.', 'info')
                return render_template('recuperar_senha.html')
            
            user_id = user['id']
            login_usuario = user['login']
            email_usuario = user['email']

            # Gerar um token com expiração de 15 minutos
            token = serializer.dumps({'user_id': user_id}, salt='recover')

            # Gerar o link de redefinição
            reset_url = url_for('redefinir_senha', token=token, _external=True)

            # Montar o e-mail (copie sua estrutura de e-mail já usada no seu sistema)
            subject = "Recuperação de senha - CODEGO"
            body = f"""
Olá {login_usuario},

Você solicitou a recuperação de sua senha no sistema CODEGO.

Para redefinir sua senha, clique no link abaixo:

{reset_url}

Este link é válido por 15 minutos apenas.

Se você não solicitou, ignore este e-mail.

Atenciosamente,
Equipe CODEGO
"""
            # Enviar o e‑mail via gmail
            try:
                # Configuração do gmail
                smtp_server = 'smtp.gmail.com'
                smtp_port = 587
                smtp_username = 'emailsendercodego@gmail.com'
                smtp_password = 'sxlf wwsk woha cxuc'

                msg = MIMEMultipart()
                msg['From'] = smtp_username
                msg['To'] = email_usuario
                msg['Subject'] = subject

                msg.attach(MIMEText(body, 'plain', 'utf-8'))

                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.sendmail(smtp_username, [email_usuario], msg.as_string())
                server.quit()

                flash('Se o e-mail for válido, enviaremos instruções de recuperação para o e-mail cadastrado.', 'info')
                return redirect(url_for('login'))

            except Exception as e:
                flash(f'Erro ao enviar e-mail: {str(e)}. Tente novamente mais tarde.', 'danger')
                return render_template('recuperar_senha.html')

        except Exception as e:
            flash(f'Erro ao processar a recuperação: {str(e)}', 'danger')
            return render_template('recuperar_senha.html')

    # Se for GET, só mostra o formulário
    return render_template('recuperar_senha.html')

@app.route('/redefinir_senha/<token>', methods=['GET', 'POST'])
def redefinir_senha(token):
    try:
        data = serializer.loads(token, salt='recover', max_age=900)
        user_id = data['user_id']
    except Exception as e:
        flash('Link inválido ou expirado.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        senha = request.form.get('senha', '').strip()
        confirmar = request.form.get('confirmar', '').strip()
        
        if not senha or senha != confirmar:
            flash('As senhas não conferem ou estão vazias.', 'danger')
            return render_template('redefinir_senha.html', token=token)

        senha_hash = bcrypt.generate_password_hash(senha).decode('utf-8')
        
        try:
            db = mysql.connector.connect(**db_config)
            cursor = db.cursor()
            cursor.execute("UPDATE usuarios SET senha = %s WHERE id = %s", (senha_hash, user_id))
            db.commit()
            cursor.close()
            db.close()
            flash('Senha alterada com sucesso!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Erro ao salvar senha: {str(e)}', 'danger')
            return render_template('redefinir_senha.html', token=token)
    
    return render_template('redefinir_senha.html', token=token)

@app.route('/logs')
def logs():
    if 'username' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    logs_data = []
    try:
        with mysql.connector.connect(**db_config) as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT user_id, username, action, descricao, timestamp FROM logs ORDER BY timestamp DESC LIMIT 1000")
                logs_data = cursor.fetchall()
    except mysql.connector.Error as err:
        print(f"Erro logs: {err}")
    return render_template('logs.html', logs=logs_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)