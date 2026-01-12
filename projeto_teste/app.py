from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd
import os
import csv
from logger_config import sistema_logger

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'

# --- Configuração de Dados ---
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

# --- Funções Auxiliares de Dados ---

def ler_csv_seguro():
    """Lê o CSV tratando erros de tokenização e garantindo a estrutura."""
    if not os.path.exists(OUTPUT_CSV):
        df_init = pd.DataFrame(columns=COLUNAS + ['USUARIO_REGISTRO', 'DATA_REGISTRO'])
        df_init.to_csv(OUTPUT_CSV, index=False, sep=';', encoding='utf-8')
        return df_init
    try:
        # on_bad_lines='skip' evita que o app trave se o CSV estiver corrompido
        return pd.read_csv(OUTPUT_CSV, sep=';', on_bad_lines='skip', encoding='utf-8', engine='python')
    except Exception as e:
        sistema_logger.error(f"Erro crítico ao ler CSV: {e}")
        return pd.DataFrame(columns=COLUNAS)

def salvar_no_csv(dados_dict):
    """Garante o salvamento correto com tratamento de aspas e metadados."""
    dados_dict['USUARIO_REGISTRO'] = session.get('username', 'sistema')
    dados_dict['DATA_REGISTRO'] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    
    colunas_completas = COLUNAS + ['USUARIO_REGISTRO', 'DATA_REGISTRO']
    novo_df = pd.DataFrame([dados_dict])
    novo_df = novo_df.reindex(columns=colunas_completas, fill_value='')

    header = not os.path.exists(OUTPUT_CSV)
    novo_df.to_csv(OUTPUT_CSV, mode='a', index=False, header=header, 
                   encoding='utf-8', sep=';', quoting=csv.QUOTE_MINIMAL)

# --- Middleware de Segurança ---

@app.before_request
def before_request_func():
    caminhos_livres = ['login', 'static', 'recuperar_senha', 'registrar_usuario']
    if 'username' not in session and request.endpoint not in caminhos_livres:
        return redirect(url_for('login'))

# --- Rotas de Autenticação ---

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

# --- Rotas de Menu ---

@app.route('/menu')
def menu():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    return render_template('menu.html')

@app.route('/menu_jur')
def menu_jur():
    if session.get('role') != 'jur': return redirect(url_for('login'))
    return render_template('menu_jur.html')

# --- Rotas de Cadastro ---

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
        dados['PROCESSO JUDICIAL'] = request.form.get('processo_judicial')
        dados['STATUS'] = request.form.get('status')
        dados['ASSUNTO JUDICIAL'] = request.form.get('assunto_judicial')
        salvar_no_csv(dados)
        flash('Registro jurídico salvo!', 'success')
        return redirect(url_for('menu_jur'))
    return render_template('cadastro_jur.html', username=session.get('username'))

# --- Funções de Edição ---

@app.route('/selecionar_edicao')
def selecionar_edicao():
    role = session.get('role')
    df = ler_csv_seguro().fillna('-')
    return render_template('selecionar_edicao.html', dados=df.to_dict(orient='records'), role=role)

@app.route('/editar/<int:row_id>', methods=['GET', 'POST'])
def editar(row_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    df = ler_csv_seguro()
    
    if request.method == 'POST':
        for col in COLUNAS[:-3]:
            df.at[row_id, col] = request.form.get(col, '')
        df.to_csv(OUTPUT_CSV, index=False, sep=';', quoting=csv.QUOTE_MINIMAL, encoding='utf-8')
        flash('Alterações administrativas salvas!', 'success')
        return redirect(url_for('menu'))

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
    return render_template('editar_jur.html', 
                           dados=dados_linha, 
                           colunas_fixas=COLUNAS[:-3], 
                           colunas_editaveis=COLUNAS[-3:], 
                           row_id=row_id)

# --- Outras Rotas ---

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

if __name__ == '__main__':
    # Inicializa o CSV se não existir
    ler_csv_seguro()
    app.run(debug=True)
    
