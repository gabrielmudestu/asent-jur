from flask import Blueprint, render_template, request, session, redirect, url_for, flash, current_app
from app.db import get_db
from app.services.log_service import gravar_log
import os
from app.utils.decorators import role_required
from app.constants import colunas_map, campos_numericos
from app.services.cadastro_service import CadastroService

cadastro_bp = Blueprint("cadastro", __name__)

@cadastro_bp.route('/cadastro', methods=['GET', 'POST'])
@role_required('assent', 'admin','assent_gestor','jur_gestor')
def cadastro():
    if request.method == 'POST':

        dados = CadastroService.normalizar_dados(request.form)

        empresa_id = None
            
        try:
            with get_db() as db:
                with db.cursor() as cursor:
                    cols = ', '.join(dados.keys())
                    placeholders = ', '.join(['%s'] * len(dados))
                    query = f"INSERT INTO municipal_lots ({cols}) VALUES ({placeholders}) RETURNING id"
                    valores = [dados[campo] for campo in dados.keys()]
                    cursor.execute(query, valores)
                    empresa_id = cursor.fetchone()[0]  # Obtém o ID do registro inserido
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
                    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], nome_arquivo)

                    file.save(filepath)

                    caminho_imagem = f"/static/imagens_empresas/{nome_arquivo}".replace('\\', '/')

                    with db.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO empresa_infos (empresa_id, descricao, caminho_imagem)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (empresa_id) DO UPDATE
                                SET descricao = EXCLUDED.descricao,
                                    caminho_imagem = EXCLUDED.caminho_imagem
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

@cadastro_bp.route('/cadastro_jur', methods=['GET', 'POST'])
@role_required('jur', 'admin''assent_gestor','jur_gestor')
def cadastro_jur():
    if request.method == 'POST':
        empresa_id = request.form.get('empresa_id')
        dados_jur = {
            'processo_judicial': request.form.get('processo_judicial', ''),
            'status': request.form.get('status', ''),
            'assunto_judicial': request.form.get('assunto_judicial', ''),
            'valor_da_causa': request.form.get('valor_da_causa', '')
        }
        
        try:
            with get_db() as db:
                with db.cursor() as cursor:
                    set_clause = ", ".join([f"{k} = %s" for k in dados_jur.keys()])
                    query = f"UPDATE municipal_lots SET {set_clause} WHERE id = %s"
                    cursor.execute(query, list(dados_jur.values()) + [empresa_id])
                    db.commit()
                    gravar_log(f"CADASTRO_JURIDICO_INICIAL (ID {empresa_id})", db_conn=db)
            flash('Informações jurídicas adicionadas com sucesso!', 'success')
            return redirect(url_for('dashboard.menu', modo='jur'))
        except Exception as e:
            flash(f'Erro ao salvar: {e}', 'danger')

    # Lógica GET: Busca empresas que não possuem dados jurídicos preenchidos
    empresas = []
    try:
        with get_db() as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("""
                    SELECT id, empresa, cnpj FROM municipal_lots 
                    WHERE empresa != '-' ORDER BY empresa
                """)
                empresas = cursor.fetchall()
    except Exception as e:
        print(f"Erro ao buscar empresas: {e}")

    return render_template('cadastro_jur.html', empresas=empresas, username=session.get('username'))