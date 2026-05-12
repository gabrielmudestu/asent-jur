from flask import Blueprint, render_template, redirect, url_for, flash, request

from app.constants import chaves_fixas, labels_fixas
from app.db import get_db
from app.services.juridico_schema_service import garantir_schema_juridico
from app.services.prazo_service import buscar_prazos_juridicos, filtrar_prazos
from app.utils.decorators import role_required

juridico_bp = Blueprint("juridico", __name__)


@juridico_bp.route('/jur/assentamento')
@role_required('jur', 'jur_gestor', 'admin')
def consultar_assentamento():
    try:
        with get_db() as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("""
                    SELECT id, municipio, distrito, empresa, cnpj, processo_sei,
                           status_de_assentamento, ramo_de_atividade, quadra,
                           modulo_s, tamanho_m2, imovel_regular_irregular
                    FROM municipal_lots
                    WHERE empresa != '-'
                    ORDER BY empresa
                """)
                dados = cursor.fetchall()
    except Exception as err:
        dados = []
        print(f"Erro ao buscar dados de assentamento para o juridico: {err}")

    return render_template('consulta_assentamento_jur.html', dados=dados)


@juridico_bp.route('/jur/assentamento/<int:empresa_id>')
@role_required('jur', 'jur_gestor', 'admin')
def detalhe_assentamento(empresa_id):
    try:
        with get_db() as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM municipal_lots WHERE id = %s", (empresa_id,))
                dados = cursor.fetchone()
    except Exception as err:
        print(f"Erro ao buscar detalhe de assentamento para o juridico: {err}")
        flash('Erro ao carregar dados de assentamento.', 'danger')
        return redirect(url_for('juridico.consultar_assentamento'))

    if not dados:
        flash('Registro de assentamento nao encontrado.', 'warning')
        return redirect(url_for('juridico.consultar_assentamento'))

    return render_template(
        'detalhe_assentamento_jur.html',
        dados=dados,
        colunas=chaves_fixas,
        labels=labels_fixas,
    )


@juridico_bp.route('/jur/prazos')
@role_required('jur', 'jur_gestor', 'admin')
def prazos_juridicos():
    filtro = request.args.get('filtro', 'alertas')
    try:
        dias_alerta = int(request.args.get('dias', 30))
    except (TypeError, ValueError):
        dias_alerta = 30
    dias_alerta = max(1, min(dias_alerta, 365))

    filtros_validos = {'alertas', 'vencido', 'hoje', 'proximo', 'futuro', 'sem_data', 'todos'}
    if filtro not in filtros_validos:
        filtro = 'alertas'

    try:
        with get_db() as db:
            garantir_schema_juridico(db)
            with db.cursor(dictionary=True) as cursor:
                prazos, resumo = buscar_prazos_juridicos(cursor, dias_alerta=dias_alerta)
                prazos_filtrados = filtrar_prazos(prazos, filtro)
    except Exception as err:
        prazos = []
        prazos_filtrados = []
        resumo = {
            'total': 0,
            'vencido': 0,
            'hoje': 0,
            'proximo': 0,
            'futuro': 0,
            'sem_data': 0,
            'alertas': 0,
        }
        print(f"Erro ao buscar prazos juridicos: {err}")
        flash('Erro ao carregar prazos juridicos.', 'danger')

    return render_template(
        'prazos_jur.html',
        prazos=prazos_filtrados,
        resumo=resumo,
        filtro=filtro,
        dias_alerta=dias_alerta,
    )
