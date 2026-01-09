from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd
import os
from logger_config import sistema_logger

app = Flask(__name__)
# Chave secreta para gerenciar sessões
app.secret_key = 'sua_chave_secreta_aqui'

# --- Configuração de Dados ---
# Cabeçalhos completos para manter a compatibilidade com o CSV original
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

# --- Rotas e Funções ---

@app.before_request
def before_request_func():
    """
    Controle de acesso: Libera páginas públicas e arquivos estáticos.
    """
    caminhos_livres = ['login', 'static', 'recuperar_senha', 'registrar_usuario']
    
    if 'username' not in session and request.endpoint not in caminhos_livres:
        return redirect(url_for('login'))

@app.route('/')
def index():
    # Se já estiver logado, manda para o menu respectivo
    if 'username' in session:
        return redirect(url_for('menu_jur' if session.get('role') == 'jur' else 'menu'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Lógica para o Administrador
        if username == 'admin' and password == '12345':
            session['username'] = username
            session['role'] = 'admin'
            sistema_logger.info(f"Admin logado. IP: {request.remote_addr}")
            return redirect(url_for('menu'))
            
        # Lógica para o Usuário Jurídico
        elif username == 'jur' and password == '12345':
            session['username'] = username
            session['role'] = 'jur'
            sistema_logger.info(f"Usuário JUR logado. IP: {request.remote_addr}")
            return redirect(url_for('menu_jur'))
            
        else:
            flash('Usuário ou senha inválidos!', 'danger')
            
    return render_template('login.html')

@app.route('/menu')
def menu():
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('menu.html')

@app.route('/menu_jur')
def menu_jur():
    if 'username' not in session or session.get('role') != 'jur':
        return redirect(url_for('login'))
    return render_template('menu_jur.html')

@app.route('/registrar-usuario', methods=['GET', 'POST'])
def registrar_usuario():
    if request.method == 'POST':
        flash('Solicitação de cadastro enviada ao administrador!', 'success')
        return redirect(url_for('login'))
    return render_template('registrar_usuario.html')

@app.route('/recuperar-senha', methods=['GET', 'POST'])
def recuperar_senha():
    if request.method == 'POST':
        email = request.form.get('email')
        flash(f'Instruções enviadas para o e-mail: {email}', 'success')
        return redirect(url_for('login'))
    return render_template('recuperar_senha.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    username = session.get('username')
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        dados_formulario = {coluna: request.form.get(coluna, '') for coluna in COLUNAS}
        dados_formulario['USUARIO_REGISTRO'] = username
        dados_formulario['DATA_REGISTRO'] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')

        novo_registro = pd.DataFrame([dados_formulario])
        
        try:
            header = not os.path.exists(OUTPUT_CSV)
            novo_registro.to_csv(OUTPUT_CSV, mode='a', index=False, header=header, encoding='utf-8', sep=';')
            sistema_logger.info(f"Usuário '{username}' salvou registro: {dados_formulario['EMPRESA']}")
            flash('Dados salvos com sucesso!', 'success')
        except Exception as e:
            sistema_logger.error(f"Erro ao salvar: {e}")
            flash(f'Erro ao salvar dados: {e}', 'danger')
        
        return redirect(url_for('cadastro'))
  
    return render_template('cadastro.html', colunas=COLUNAS, username=username)

@app.route('/cadastro_jur', methods=['GET', 'POST'])
def cadastro_jur():
    """
    Formulário específico para o usuário Jurídico com campos reduzidos.
    """
    username = session.get('username')
    if 'username' not in session or session.get('role') != 'jur':
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Cria um dicionário com todas as colunas vazias
        dados_completos = {coluna: '' for coluna in COLUNAS}
        
        # Preenche apenas os campos solicitados do formulário jurídico
        dados_completos['PROCESSO JUDICIAL'] = request.form.get('processo_judicial', '')
        dados_completos['STATUS'] = request.form.get('status', '')
        dados_completos['ASSUNTO JUDICIAL'] = request.form.get('assunto_judicial', '')
        
        # Metadados
        dados_completos['USUARIO_REGISTRO'] = username
        dados_completos['DATA_REGISTRO'] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')

        novo_registro = pd.DataFrame([dados_completos])
        
        try:
            header = not os.path.exists(OUTPUT_CSV)
            novo_registro.to_csv(OUTPUT_CSV, mode='a', index=False, header=header, encoding='utf-8', sep=';')
            sistema_logger.info(f"Usuário Jurídico '{username}' salvou processo: {dados_completos['PROCESSO JUDICIAL']}")
            flash('Registro jurídico salvo com sucesso!', 'success')
        except Exception as e:
            sistema_logger.error(f"Erro ao salvar registro jurídico: {e}")
            flash(f'Erro ao salvar dados: {e}', 'danger')
            
        return redirect(url_for('menu_jur'))

    return render_template('cadastro_jur.html', username=username)

@app.route('/logout')
def logout():
    if 'username' in session:
        sistema_logger.info(f"Usuário '{session['username']}' deslogou.")
        session.clear()
        flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    if not os.path.exists(OUTPUT_CSV):
        pd.DataFrame(columns=COLUNAS).to_csv(OUTPUT_CSV, index=False, sep=';')
        
    sistema_logger.info("Aplicação Flask iniciada.")
    app.run(debug=True)