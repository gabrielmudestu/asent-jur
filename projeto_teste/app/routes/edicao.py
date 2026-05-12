import os

from flask import Blueprint, render_template, session, redirect, url_for, flash, request, abort, send_file

from app.db import get_db
from app.services.log_service import gravar_log
from app.services.cadastro_service import CadastroService
from app.services.juridico_schema_service import garantir_schema_juridico
from app.services.processo_documento_service import salvar_documento_processo
from app.services.processo_historico_service import (
    historico_documento_anexado,
    historico_edicao,
    montar_alteracoes_processo,
    registrar_historico_processo,
)
from app.services.processo_busca_service import buscar_processos_juridicos, contar_processos_juridicos
from app.constants import (
    COLUNAS,
    LABELS,
    chaves_fixas,
    labels_fixas,
    ramo_de_atividade_opcoes,
    status_opcoes,
    status_de_assentamento_opcoes,
    acao_judicial_opcoes,
    imovel_opcoes,
)
from app.utils.decorators import role_required


edicao_bp = Blueprint("edicao", __name__)


def salvar_vinculos_processo(cursor, processo_id, partes, eventos):
    cursor.execute("DELETE FROM processo_partes WHERE processo_id = %s", (processo_id,))
    cursor.execute("DELETE FROM processo_eventos WHERE processo_id = %s AND categoria <> 'historico'", (processo_id,))

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


@edicao_bp.route('/selecionar_edicao/<modo>')
@role_required('assent', 'admin', 'jur', 'assent_gestor', 'jur_gestor')
def selecionar_edicao(modo):
    role = session.get('role')
    termo_busca = request.args.get('q', '').strip()
    pagina = request.args.get('page', 1, type=int)
    itens_por_pagina = 50
    if pagina < 1:
        pagina = 1
    paginacao = None

    if modo == 'assent' and role not in ['assent', 'admin', 'assent_gestor']:
        abort(403)

    if modo == 'jur' and role not in ['jur', 'admin', 'jur_gestor']:
        abort(403)

    try:
        with get_db() as db:
            if modo == 'jur':
                garantir_schema_juridico(db)
            with db.cursor(dictionary=True) as cursor:
                if modo == 'jur':
                    total_registros = contar_processos_juridicos(cursor, termo_busca)
                    total_paginas = max(1, (total_registros + itens_por_pagina - 1) // itens_por_pagina)
                    if pagina > total_paginas:
                        pagina = total_paginas
                    offset = (pagina - 1) * itens_por_pagina
                    dados = buscar_processos_juridicos(
                        cursor,
                        termo_busca,
                        limite=itens_por_pagina,
                        offset=offset,
                    )
                    paginacao = {
                        'pagina': pagina,
                        'itens_por_pagina': itens_por_pagina,
                        'total_registros': total_registros,
                        'total_paginas': total_paginas,
                        'inicio': offset + 1 if total_registros else 0,
                        'fim': min(offset + itens_por_pagina, total_registros),
                        'tem_anterior': pagina > 1,
                        'tem_proxima': pagina < total_paginas,
                    }
                else:
                    cursor.execute("""
                        SELECT id, municipio, empresa, cnpj
                        FROM municipal_lots
                        WHERE empresa != '-'
                        ORDER BY empresa
                    """)
                    dados = cursor.fetchall()
    except Exception as err:
        dados = []
        print(f"Erro ao buscar dados: {err}")

    return render_template(
        'selecionar_edicao.html',
        dados=dados,
        modo=modo,
        termo_busca=termo_busca,
        paginacao=paginacao,
    )


@edicao_bp.route('/editar/<int:empresa_id>', methods=['GET', 'POST'])
@role_required('assent', 'admin', 'assent_gestor')
def editar(empresa_id):
    try:
        with get_db() as db:
            garantir_schema_juridico(db)
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM municipal_lots WHERE id = %s", (empresa_id,))
                empresa = cursor.fetchone()
                if not empresa:
                    flash('Empresa nao encontrada.', 'danger')
                    return redirect(url_for('edicao.selecionar_edicao', modo='assent'))

                if request.method == 'POST':
                    campos = COLUNAS[:-4]
                    set_clause = ', '.join([f"`{col}` = %s" for col in campos])
                    query = f"UPDATE municipal_lots SET {set_clause} WHERE id = %s"
                    valores = []
                    alteracoes = []
                    dados_normalizados = CadastroService.normalizar_dados_edicao(request.form, campos)

                    for col in campos:
                        valor_final = dados_normalizados[col]
                        valor_velho_banco = empresa.get(col)

                        if col in CadastroService.INT_FIELDS:
                            try:
                                valor_velho = int(valor_velho_banco) if valor_velho_banco not in ('', None) else 0
                            except (ValueError, TypeError):
                                valor_velho = 0
                        elif col in CadastroService.DECIMAL_FIELDS:
                            try:
                                valor_velho = CadastroService._parse_decimal(str(valor_velho_banco), LABELS[col]) if valor_velho_banco not in ('', None) else 0
                            except (ValueError, TypeError):
                                valor_velho = 0
                        else:
                            valor_velho = str(valor_velho_banco) if valor_velho_banco not in ('', None) else '-'

                        if valor_final != valor_velho:
                            alteracoes.append(f"{LABELS[col]}: '{valor_velho}' -> '{valor_final}'")

                        valores.append(valor_final)

                    valores.append(empresa_id)
                    cursor.execute(query, valores)
                    db.commit()

                    empresa_nome = empresa['empresa'] or f'empresa {empresa_id}'
                    descricao_log = f"Empresa: {empresa_nome} (ID {empresa_id})"
                    if alteracoes:
                        descricao_log += " | Alteracoes: " + "; ".join(alteracoes)
                    else:
                        descricao_log += " | Nenhuma alteracao realizada."

                    gravar_log(
                        acao="EDICAO_EMPRESA",
                        descricao=descricao_log,
                        usuario_username=session.get('username'),
                        db_conn=db
                    )
                    flash('Alteracoes salvas!', 'success')
                    return redirect(url_for('edicao.selecionar_edicao', modo='assent'))

                return render_template(
                    'editar.html',
                    dados=empresa,
                    colunas=chaves_fixas,
                    labels=labels_fixas,
                    empresa_id=empresa_id,
                    ramo_de_atividade_opcoes=ramo_de_atividade_opcoes,
                    status_de_assentamento_opcoes=status_de_assentamento_opcoes,
                    imovel_opcoes=imovel_opcoes,
                    acao_judicial_opcoes=acao_judicial_opcoes,
                )
    except Exception as e:
        flash(f'Erro ao editar: {e}', 'danger')
        return redirect(url_for('edicao.selecionar_edicao', modo='assent'))


@edicao_bp.route('/editar_jur/<int:processo_id>', methods=['GET', 'POST'])
@role_required('jur', 'admin', 'jur_gestor')
def editar_jur(processo_id):
    try:
        with get_db() as db:
            garantir_schema_juridico(db)
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("""
                    SELECT id, numero_processo, titulo, descricao, tipo_acao, tipo_processo,
                           tribunal, vara, comarca, valor_da_causa, status, fase,
                           data_criacao, assunto_judicial, recurso_acionado, tipo_recurso
                    FROM processos
                    WHERE id = %s
                """, (processo_id,))

                processo_atual = cursor.fetchone()
                if not processo_atual:
                    flash('Processo nao encontrado.', 'danger')
                    return redirect(url_for('edicao.selecionar_edicao', modo='jur'))

                if request.method == 'POST':
                    cursor.execute("SELECT * FROM processo_partes WHERE processo_id = %s ORDER BY id", (processo_id,))
                    partes_antigas = cursor.fetchall()
                    cursor.execute("SELECT * FROM processo_eventos WHERE processo_id = %s AND categoria <> 'historico' ORDER BY id", (processo_id,))
                    eventos_antigos = cursor.fetchall()

                    processo = CadastroService.normalizar_processo_juridico(request.form)
                    partes, eventos = CadastroService.normalizar_vinculos_processo(request.form)
                    alteracoes = montar_alteracoes_processo(
                        processo_atual,
                        processo,
                        partes_antigas=partes_antigas,
                        partes_novas=partes,
                        eventos_antigos=eventos_antigos,
                        eventos_novos=eventos,
                    )
                    cursor.execute("""
                        UPDATE processos
                        SET numero_processo = %s,
                            titulo = %s,
                            descricao = %s,
                            tipo_acao = %s,
                            tipo_processo = %s,
                            tribunal = %s,
                            vara = %s,
                            comarca = %s,
                            valor_da_causa = %s,
                            status = %s,
                            fase = %s,
                            data_criacao = %s,
                            assunto_judicial = %s,
                            recurso_acionado = %s,
                            tipo_recurso = %s
                        WHERE id = %s
                    """, (
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
                        processo_id,
                    ))
                    salvar_vinculos_processo(cursor, processo_id, partes, eventos)
                    documento_id = salvar_documento_processo(cursor, processo_id, request.files.get('documento_arquivo'), request.form)
                    if documento_id:
                        titulo, descricao = historico_documento_anexado(
                            session.get('username', 'sistema'),
                            request.form.get('documento_nome'),
                            origem='edicao do processo',
                        )
                        registrar_historico_processo(cursor, processo_id, titulo, descricao)

                    titulo, descricao = historico_edicao(session.get('username', 'sistema'), alteracoes)
                    registrar_historico_processo(cursor, processo_id, titulo, descricao)

                    db.commit()
                    gravar_log(
                        acao="EDICAO_PROCESSO",
                        descricao=f"Processo juridico atualizado: {processo['numero_processo']} (ID {processo_id})",
                        usuario_username=session.get('username'),
                        db_conn=db
                    )
                    flash('Processo atualizado!', 'success')
                    return redirect(url_for('edicao.selecionar_edicao', modo='jur'))

                cursor.execute("SELECT * FROM processo_partes WHERE processo_id = %s ORDER BY id", (processo_id,))
                partes = cursor.fetchall()
                cursor.execute("SELECT * FROM processo_eventos WHERE processo_id = %s ORDER BY id", (processo_id,))
                eventos = cursor.fetchall()
                cursor.execute("""
                    SELECT *
                    FROM processo_documentos
                    WHERE processo_id = %s
                    ORDER BY COALESCE(data_documento, created_at) DESC, id DESC
                """, (processo_id,))
                documentos_anexos = cursor.fetchall()

                return render_template(
                    'editar_jur.html',
                    processo=processo_atual,
                    partes=partes,
                    eventos=eventos,
                    documentos_anexos=documentos_anexos,
                    processo_id=processo_id,
                    status_opcoes=status_opcoes,
                )
    except Exception as e:
        flash(f'Erro ao editar juridico: {e}', 'danger')
        return redirect(url_for('edicao.selecionar_edicao', modo='jur'))


@edicao_bp.route('/processo_jur/<int:processo_id>')
@role_required('jur', 'admin', 'jur_gestor')
def detalhe_jur(processo_id):
    try:
        with get_db() as db:
            garantir_schema_juridico(db)
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("""
                    SELECT id, numero_processo, titulo, descricao, tipo_acao, tipo_processo,
                           tribunal, vara, comarca, valor_da_causa, status, fase,
                           data_criacao, assunto_judicial, recurso_acionado, tipo_recurso
                    FROM processos
                    WHERE id = %s
                """, (processo_id,))
                processo = cursor.fetchone()

                if not processo:
                    flash('Processo nao encontrado.', 'warning')
                    return redirect(url_for('edicao.selecionar_edicao', modo='jur'))

                cursor.execute("SELECT * FROM processo_partes WHERE processo_id = %s ORDER BY id", (processo_id,))
                partes = cursor.fetchall()
                cursor.execute("""
                    SELECT *
                    FROM processo_eventos
                    WHERE processo_id = %s
                    ORDER BY COALESCE(data_evento, created_at) DESC, id DESC
                """, (processo_id,))
                eventos = cursor.fetchall()
                cursor.execute("""
                    SELECT *
                    FROM processo_documentos
                    WHERE processo_id = %s
                    ORDER BY COALESCE(data_documento, created_at) DESC, id DESC
                """, (processo_id,))
                documentos_anexos = cursor.fetchall()

        return render_template(
            'detalhe_jur.html',
            processo=processo,
            partes=partes,
            eventos=eventos,
            documentos_anexos=documentos_anexos,
            processo_id=processo_id,
        )
    except Exception as e:
        flash(f'Erro ao carregar processo: {e}', 'danger')
        return redirect(url_for('edicao.selecionar_edicao', modo='jur'))


@edicao_bp.route('/processo_jur/documento/<int:documento_id>')
@role_required('jur', 'admin', 'jur_gestor')
def baixar_documento_jur(documento_id):
    try:
        with get_db() as db:
            garantir_schema_juridico(db)
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("""
                    SELECT *
                    FROM processo_documentos
                    WHERE id = %s
                    LIMIT 1
                """, (documento_id,))
                documento = cursor.fetchone()

        if not documento:
            flash('Documento nao encontrado.', 'warning')
            return redirect(url_for('edicao.selecionar_edicao', modo='jur'))

        caminho = documento['caminho_arquivo']
        if not caminho or not os.path.exists(caminho):
            flash('Arquivo do documento nao encontrado no servidor.', 'danger')
            return redirect(url_for('edicao.detalhe_jur', processo_id=documento['processo_id']))

        return send_file(
            caminho,
            as_attachment=True,
            download_name=documento['nome_arquivo_original'],
            mimetype=documento.get('content_type') or None,
        )
    except Exception as e:
        flash(f'Erro ao baixar documento: {e}', 'danger')
        return redirect(url_for('edicao.selecionar_edicao', modo='jur'))
