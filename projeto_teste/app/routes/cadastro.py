from flask import Blueprint, render_template, request, session, redirect, url_for, flash, current_app
from app.db import get_db
from app.services.log_service import gravar_log
import os
from app.utils.decorators import role_required
from app.constants import campos_numericos, colunas_map, imovel_opcoes, ramo_de_atividade_opcoes, status_de_assentamento_opcoes
from app.services.cadastro_service import CadastroService

cadastro_bp = Blueprint("cadastro", __name__)

@cadastro_bp.route('/cadastro', methods=['GET', 'POST'])
@role_required('assent', 'admin','assent_gestor')
def cadastro():
    if request.method == 'POST':

        dados = CadastroService.normalizar_dados(request.form)

        empresa_id = None
            
        try:
            with get_db() as db:
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
                    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], nome_arquivo)

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
    return render_template(
        'cadastro.html',
        username=session.get('username'),
        ramo_de_atividade_opcoes=ramo_de_atividade_opcoes,
        status_de_assentamento_opcoes=status_de_assentamento_opcoes,
        imovel_opcoes=imovel_opcoes,
    )

@cadastro_bp.route('/cadastro_jur', methods=['GET', 'POST'])
@role_required('jur', 'admin','jur_gestor')
def cadastro_jur():
    if request.method == 'POST':
        empresa_id = request.form.get('empresa_id')
        
        try:
            processo = CadastroService.normalizar_processo_juridico(request.form)
            with get_db() as db:
                with db.cursor() as cursor:
                    cursor.execute(
                        """
                            INSERT INTO processos
                            (empresa_id, numero_processo, tipo_processo, status, assunto_judicial,
                             valor_da_causa, recurso_acionado, tipo_recurso)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            empresa_id,
                            processo['numero_processo'],
                            processo['tipo_processo'],
                            processo['status'],
                            processo['assunto_judicial'],
                            processo['valor_da_causa'],
                            processo['recurso_acionado'],
                            processo['tipo_recurso'],
                        )
                    )
                    db.commit()
                    gravar_log(
                        acao=f"CADASTRO_PROCESSO_JURIDICO (ID {empresa_id})",
                        descricao=(
                            f"numero_processo: {processo['numero_processo']} | tipo_processo: {processo['tipo_processo']} | "
                            f"status: {processo['status']} | assunto_judicial: {processo['assunto_judicial']} | "
                            f"valor_da_causa: {processo['valor_da_causa'] if processo['valor_da_causa'] is not None else '-'} | "
                            f"recurso_acionado: {processo['recurso_acionado']} | "
                            f"tipo_recurso: {processo['tipo_recurso'] or '-'}"
                        ),
                        usuario_username=session.get('username'),
                        db_conn=db
                    )
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
