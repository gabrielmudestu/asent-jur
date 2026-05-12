import os
import csv
from uuid import uuid4

from flask import Blueprint, render_template, request, session, redirect, url_for, flash, current_app, send_file
from werkzeug.utils import secure_filename

from app.db import get_db
from app.services.log_service import gravar_log
from app.utils.decorators import role_required
from app.constants import imovel_opcoes, ramo_de_atividade_opcoes, status_de_assentamento_opcoes
from app.services.cadastro_service import CadastroService
from app.services.importacao_processos_service import (
    OPCOES_CAMPOS_IMPORTACAO,
    ler_planilha_processos_detalhada,
    preparar_processos_importacao,
)
from app.services.juridico_schema_service import garantir_schema_juridico
from app.services.processo_documento_service import salvar_documento_processo
from app.services.processo_historico_service import (
    historico_criacao_manual,
    historico_documento_anexado,
    historico_importacao,
    historico_importacao_duplicada,
    registrar_historico_processo,
)


cadastro_bp = Blueprint("cadastro", __name__)


def pasta_importacoes_processos():
    caminho = os.path.join(current_app.root_path, 'uploads', 'importacoes_processos')
    os.makedirs(caminho, exist_ok=True)
    return caminho


def pasta_relatorios_erros_importacao():
    caminho = os.path.join(current_app.root_path, 'uploads', 'relatorios_erros_importacao')
    os.makedirs(caminho, exist_ok=True)
    return caminho


def salvar_arquivo_importacao(arquivo):
    nome_original = secure_filename(arquivo.filename or 'processos.csv')
    extensao = os.path.splitext(nome_original)[1].lower()
    if extensao not in {'.csv', '.xlsx'}:
        raise ValueError('Envie um arquivo .xlsx ou .csv.')
    nome_temporario = f"{uuid4().hex}{extensao}"
    caminho = os.path.join(pasta_importacoes_processos(), nome_temporario)
    arquivo.save(caminho)
    return nome_temporario, nome_original


def abrir_arquivo_importacao(nome_temporario, nome_original):
    nome_seguro = secure_filename(nome_temporario or '')
    caminho = os.path.join(pasta_importacoes_processos(), nome_seguro)
    if not nome_seguro or not os.path.exists(caminho):
        raise ValueError('Arquivo temporario de importacao nao encontrado. Envie a planilha novamente.')
    arquivo = open(caminho, 'rb')
    arquivo.filename = nome_original
    return arquivo


def extrair_mapeamento_importacao(form):
    mapeamento = {}
    total_colunas = int(form.get('total_colunas') or 0)
    for indice in range(total_colunas):
        coluna = form.get(f'coluna_{indice}')
        campo = form.get(f'campo_{indice}')
        if coluna is not None:
            mapeamento[coluna] = campo or ''
    return mapeamento


def salvar_relatorio_erros_importacao(erros):
    if not erros:
        return None
    nome = f"erros_importacao_{uuid4().hex}.csv"
    caminho = os.path.join(pasta_relatorios_erros_importacao(), nome)
    with open(caminho, 'w', newline='', encoding='utf-8-sig') as arquivo_csv:
        escritor = csv.writer(arquivo_csv, delimiter=';')
        escritor.writerow(['erro'])
        for erro in erros:
            escritor.writerow([erro])
    return nome


def montar_previa_importacao(nome_temporario, nome_original, mapeamento=None):
    with abrir_arquivo_importacao(nome_temporario, nome_original) as arquivo:
        detalhe = ler_planilha_processos_detalhada(arquivo)

    with abrir_arquivo_importacao(nome_temporario, nome_original) as arquivo:
        processos, erros = preparar_processos_importacao(arquivo, mapeamento_colunas=mapeamento)

    mapeamento_atual = {}
    for coluna in detalhe['cabecalho']:
        if mapeamento is not None and coluna in mapeamento:
            mapeamento_atual[coluna] = mapeamento[coluna]
        else:
            mapeamento_atual[coluna] = detalhe['mapeamento_detectado'].get(coluna) or ''

    return {
        'temp_name': nome_temporario,
        'original_filename': nome_original,
        'cabecalho': detalhe['cabecalho'],
        'mapeamento': mapeamento_atual,
        'opcoes_campos': OPCOES_CAMPOS_IMPORTACAO,
        'amostra': processos[:10],
        'validos': len(processos),
        'erros': erros,
        'relatorio_erros': salvar_relatorio_erros_importacao(erros),
    }


def salvar_vinculos_processo(cursor, processo_id, partes, eventos):
    for parte in partes:
        cursor.execute("""
            INSERT INTO processo_partes
            (processo_id, papel, nome, tipo_parte, contato, observacoes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            processo_id,
            parte['papel'],
            parte['nome'],
            parte['tipo_parte'],
            parte['contato'],
            parte['observacoes'],
        ))

    for evento in eventos:
        cursor.execute("""
            INSERT INTO processo_eventos
            (processo_id, categoria, titulo, descricao, data_evento)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            processo_id,
            evento['categoria'],
            evento['titulo'],
            evento['descricao'],
            evento['data_evento'],
        ))


def inserir_processo_juridico(cursor, processo, partes, eventos, historico):
    cursor.execute(
        """
            INSERT INTO processos
            (numero_processo, titulo, descricao, tipo_acao, tipo_processo,
             tribunal, vara, comarca, valor_da_causa, status, fase,
             data_criacao, assunto_judicial, recurso_acionado, tipo_recurso)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            processo['numero_processo'],
            processo['titulo'],
            processo['descricao'],
            processo['tipo_acao'],
            processo['tipo_processo'],
            processo['tribunal'],
            processo['vara'],
            processo['comarca'],
            processo['valor_da_causa'],
            processo['status'],
            processo['fase'],
            processo['data_criacao'],
            processo['assunto_judicial'],
            processo['recurso_acionado'],
            processo['tipo_recurso'],
        )
    )
    processo_id = cursor.lastrowid
    salvar_vinculos_processo(cursor, processo_id, partes, eventos)
    registrar_historico_processo(cursor, processo_id, historico[0], historico[1])
    return processo_id


@cadastro_bp.route('/cadastro', methods=['GET', 'POST'])
@role_required('assent', 'admin', 'assent_gestor')
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
                        descricao=" | ".join([f"{campo}: {valor}" for campo, valor in dados.items()]),
                        usuario_username=session.get('username'),
                        db_conn=db
                    )

                if not empresa_id:
                    raise Exception("Erro ao obter ID do cadastro.")

                file = request.files.get('IMAGEM_EMPRESA')
                descricao = request.form.get('DESCRICAO_EMPRESA', '') or ' '

                if file and file.filename.strip():
                    nome_original = file.filename
                    _, ext = os.path.splitext(nome_original)
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
            return redirect(url_for('cadastro.cadastro'))
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
@role_required('jur', 'admin', 'jur_gestor')
def cadastro_jur():
    if request.method == 'POST':
        try:
            processo = CadastroService.normalizar_processo_juridico(request.form)
            partes, eventos = CadastroService.normalizar_vinculos_processo(request.form)
            usuario = session.get('username', 'sistema')
            with get_db() as db:
                garantir_schema_juridico(db)
                with db.cursor() as cursor:
                    processo_id = inserir_processo_juridico(
                        cursor,
                        processo,
                        partes,
                        eventos,
                        historico_criacao_manual(usuario, processo)
                    )
                    documento_id = salvar_documento_processo(cursor, processo_id, request.files.get('documento_arquivo'), request.form)
                    if documento_id:
                        titulo, descricao = historico_documento_anexado(
                            usuario,
                            request.form.get('documento_nome'),
                            origem='cadastro do processo',
                        )
                        registrar_historico_processo(cursor, processo_id, titulo, descricao)
                    db.commit()
                    gravar_log(
                        acao="CADASTRO_PROCESSO_JURIDICO",
                        descricao=(
                            f"numero_cnj: {processo['numero_processo']} | titulo: {processo['titulo']} | "
                            f"tipo_acao: {processo['tipo_acao']} | status: {processo['status']} | "
                            f"fase: {processo['fase'] or '-'}"
                        ),
                        usuario_username=session.get('username'),
                        db_conn=db
                    )
            flash('Informacoes juridicas adicionadas com sucesso!', 'success')
            return redirect(url_for('dashboard.menu', modo='jur'))
        except Exception as e:
            flash(f'Erro ao salvar: {e}', 'danger')

    return render_template('cadastro_jur.html', username=session.get('username'))


@cadastro_bp.route('/importar_processos_jur', methods=['GET', 'POST'])
@role_required('jur', 'admin', 'jur_gestor')
def importar_processos_jur():
    resultado = None
    previa = None

    if request.method == 'POST':
        acao = request.form.get('acao') or 'preview'

        try:
            if acao == 'preview':
                arquivo = request.files.get('arquivo_processos')
                if not arquivo or not arquivo.filename:
                    flash('Selecione uma planilha .xlsx ou .csv.', 'warning')
                    return redirect(url_for('cadastro.importar_processos_jur'))

                nome_temporario, nome_original = salvar_arquivo_importacao(arquivo)
                previa = montar_previa_importacao(nome_temporario, nome_original)
                return render_template('importar_processos_jur.html', resultado=None, previa=previa)

            nome_temporario = request.form.get('temp_name')
            nome_original = request.form.get('original_filename') or 'processos.csv'
            mapeamento = extrair_mapeamento_importacao(request.form)

            if acao == 'revisar':
                previa = montar_previa_importacao(nome_temporario, nome_original, mapeamento=mapeamento)
                return render_template('importar_processos_jur.html', resultado=None, previa=previa)

            usuario = session.get('username', 'sistema')
            nome_arquivo = nome_original
            with abrir_arquivo_importacao(nome_temporario, nome_original) as arquivo:
                processos, erros = preparar_processos_importacao(arquivo, mapeamento_colunas=mapeamento)
            importados = 0
            duplicados = 0

            with get_db() as db:
                garantir_schema_juridico(db)
                with db.cursor(dictionary=True) as cursor:
                    for item in processos:
                        numero = item['processo']['numero_processo']
                        cursor.execute("SELECT id FROM processos WHERE numero_processo = %s LIMIT 1", (numero,))
                        processo_existente = cursor.fetchone()
                        if processo_existente:
                            titulo, descricao = historico_importacao_duplicada(
                                usuario,
                                numero,
                                nome_arquivo,
                                item['linha'],
                            )
                            registrar_historico_processo(cursor, processo_existente['id'], titulo, descricao)
                            duplicados += 1
                            continue

                        inserir_processo_juridico(
                            cursor,
                            item['processo'],
                            item['partes'],
                            item['eventos'],
                            historico_importacao(usuario, item['processo'], nome_arquivo, item['linha'])
                        )
                        importados += 1

                    db.commit()
                    gravar_log(
                        acao="IMPORTACAO_PROCESSOS_JURIDICOS",
                        descricao=f"Importados: {importados} | Duplicados: {duplicados} | Erros: {len(erros)}",
                        usuario_username=session.get('username'),
                        db_conn=db
                    )

            resultado = {
                'importados': importados,
                'duplicados': duplicados,
                'erros': erros,
                'validos': len(processos),
                'relatorio_erros': salvar_relatorio_erros_importacao(erros),
            }
            flash('Importacao concluida.', 'success')
        except Exception as e:
            flash(f'Erro ao importar processos: {e}', 'danger')

    return render_template('importar_processos_jur.html', resultado=resultado, previa=previa)


@cadastro_bp.route('/importar_processos_jur/erros/<path:nome_arquivo>')
@role_required('jur', 'admin', 'jur_gestor')
def baixar_erros_importacao_processos(nome_arquivo):
    nome_seguro = secure_filename(nome_arquivo)
    caminho = os.path.join(pasta_relatorios_erros_importacao(), nome_seguro)
    if not nome_seguro or not os.path.exists(caminho):
        flash('Relatorio de erros nao encontrado.', 'warning')
        return redirect(url_for('cadastro.importar_processos_jur'))
    return send_file(
        caminho,
        as_attachment=True,
        download_name='erros_importacao_processos.csv',
        mimetype='text/csv',
    )
