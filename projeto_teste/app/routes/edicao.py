from flask import Blueprint, render_template, session, redirect, url_for, flash, request, abort
from app.db import get_db
from app.services.log_service import gravar_log
from app.constants import COLUNAS, LABELS, chaves_fixas, labels_fixas, chaves_editaveis, labels_editaveis, ramo_de_atividade_opcoes, status_opcoes, status_de_assentamento_opcoes, acao_judicial_opcoes, imovel_opcoes
from app.utils.decorators import role_required


edicao_bp = Blueprint("edicao", __name__)

@edicao_bp.route('/selecionar_edicao/<modo>')
@role_required('assent', 'admin', 'jur', 'assent_gestor','jur_gestor')
def selecionar_edicao(modo):

    role = session.get('role')

    if modo == 'assent' and role not in ['assent', 'admin', 'assent_gestor']:
        abort(403)

    if modo == 'jur' and role not in ['jur', 'admin','jur_gestor']:
        abort(403)

    try:
        with get_db() as db:
            with db.cursor(dictionary=True) as cursor:
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
    return render_template('selecionar_edicao.html', dados=dados, modo=modo)

@edicao_bp.route('/editar/<int:empresa_id>', methods=['GET', 'POST'])
@role_required('assent', 'admin', 'assent_gestor')
def editar(empresa_id):
    try:
        with get_db() as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM municipal_lots WHERE id = %s", (empresa_id,))
                empresa = cursor.fetchone()
                if not empresa:
                    flash('Empresa não encontrada.', 'danger')
                    return redirect(url_for('edicao.selecionar_edicao', modo='assent'))
                
                if request.method == 'POST':
                    campos_numericos = [
                        'processo_sei', 'empregos_gerados', 'quadra', 'qtd_modulos',
                        'tamanho_m2', 'matricula_s', 'taxa_e_ocupacao_do_imovel'
                    ]

                    campos = COLUNAS[:-4] # Pega as chaves fixas
                    set_clause = ', '.join([f"{col} = %s" for col in campos])
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
                    return redirect(url_for('edicao.selecionar_edicao', modo='assent'))
                return render_template('editar.html', dados=empresa, colunas=chaves_fixas, labels=labels_fixas, empresa_id=empresa_id, ramo_de_atividade_opcoes=ramo_de_atividade_opcoes, status_de_assentamento_opcoes=status_de_assentamento_opcoes, imovel_opcoes=imovel_opcoes, acao_judicial_opcoes=acao_judicial_opcoes)
    except Exception as e:
        flash(f'Erro ao editar: {e}', 'danger')
        return redirect(url_for('edicao.selecionar_edicao', modo='assent'))
    
@edicao_bp.route('/editar_jur/<int:empresa_id>', methods=['GET', 'POST'])
@role_required('jur', 'admin' 'assent_gestor','jur_gestor')
def editar_jur(empresa_id):
    try:
        with get_db() as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM municipal_lots WHERE id = %s", (empresa_id,))
                empresa = cursor.fetchone()
                if not empresa:
                    flash('Empresa não encontrada.', 'danger')
                    return redirect(url_for('edicao.selecionar_edicao', modo='jur'))
                
                cursor.execute("""
                SELECT id, numero_processo, status, assunto_judicial, valor_da_causa
                FROM processos
                WHERE empresa_id = %s
                """, (empresa_id,))

                processos = cursor.fetchall()
                
                if request.method == 'POST':

                    numeros = request.form.getlist("numero_processo[]")
                    status = request.form.getlist("status[]")
                    assuntos = request.form.getlist("assunto_judicial[]")
                    valores = request.form.getlist("valor_da_causa[]")
                    tipos = request.form.getlist('tipo_processo[]')
                    recursos = request.form.getlist('recurso_acionado[]')
                    tipos_recurso = request.form.getlist('tipo_recurso[]')

                    # Remove processos antigos
                    cursor.execute("DELETE FROM processos WHERE empresa_id = %s", (empresa_id,))

                    # Insere novamente
                    for i in range(len(numeros)):

                        numero = numeros[i].strip()

                        if not numero:
                            continue

                        status_val = status[i].strip()
                        assunto = assuntos[i].strip()
                        valor = valores[i].strip()

                        cursor.execute("""
                        INSERT INTO processos
                        (empresa_id, numero_processo, status, assunto_judicial, valor_da_causa, tipo_processo, recurso_acionado, tipo_recurso)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            empresa_id,
                            numero,
                            status_val,
                            assunto,
                            valor if valor else None,
                            tipos[i] if i < len(tipos) else None,
                            1 if i < len(recursos) else 0,
                            tipos_recurso[i] if i < len(tipos_recurso) else None
                        ))

                    db.commit()

                    empresa_nome = empresa['empresa'] or f'empresa {empresa_id}'

                    gravar_log(
                        acao="EDIÇÃO_PROCESSOS",
                        descricao=f"Processos jurídicos atualizados da empresa {empresa_nome} (ID {empresa_id})",
                        usuario_username=session.get('username'),
                        db_conn=db
                    )

                    flash('Processos atualizados!', 'success')

                    return redirect(url_for('edicao.selecionar_edicao', modo='jur'))
                return render_template('editar_jur.html', dados=empresa, processos=processos, colunas_fixas=chaves_fixas, colunas_editaveis=chaves_editaveis, labels=labels_fixas, labels_editaveis=labels_editaveis, empresa_id=empresa_id, status_opcoes=status_opcoes)
    except Exception as e:
        flash(f'Erro ao editar jurídico: {e}', 'danger')
        return redirect(url_for('edicao.selecionar_edicao', modo='jur'))
