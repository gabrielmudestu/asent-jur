from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from app.db import get_db
from app.services.log_service import gravar_log
from app.constants import COLUNAS, LABELS, chaves_fixas, labels_fixas, chaves_editaveis, labels_editaveis
from app.utils.decorators import role_required

edicao_bp = Blueprint("edicao", __name__)

@edicao_bp.route('/selecionar_edicao')
@role_required('assent', 'admin', 'jur')
def selecionar_edicao():
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
    return render_template('selecionar_edicao.html', dados=dados, role=session.get('role'))

@edicao_bp.route('/editar/<int:empresa_id>', methods=['GET', 'POST'])
@role_required('assent', 'admin')
def editar(empresa_id):
    try:
        with get_db() as db:
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
    
@edicao_bp.route('/editar_jur/<int:empresa_id>', methods=['GET', 'POST'])
@role_required('jur', 'admin')
def editar_jur(empresa_id):
    try:
        with get_db() as db:
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
