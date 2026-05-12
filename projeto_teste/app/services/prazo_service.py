import re
from datetime import date, datetime, timedelta


DATA_BR_PATTERN = re.compile(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b')
DATA_ISO_PATTERN = re.compile(r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b')


def _normalizar_ano(ano):
    ano = int(ano)
    if ano < 100:
        return 2000 + ano if ano < 70 else 1900 + ano
    return ano


def extrair_data_prazo(*valores):
    for valor in valores:
        if not valor:
            continue

        if isinstance(valor, date):
            return valor

        texto = str(valor)

        match_iso = DATA_ISO_PATTERN.search(texto)
        if match_iso:
            ano, mes, dia = match_iso.groups()
            try:
                return date(int(ano), int(mes), int(dia))
            except ValueError:
                pass

        match_br = DATA_BR_PATTERN.search(texto)
        if match_br:
            dia, mes, ano = match_br.groups()
            try:
                return date(_normalizar_ano(ano), int(mes), int(dia))
            except ValueError:
                pass

    return None


def classificar_prazo(data_prazo, hoje=None, dias_alerta=30):
    hoje = hoje or date.today()
    if not data_prazo:
        return 'sem_data', None

    dias = (data_prazo - hoje).days
    if dias < 0:
        return 'vencido', dias
    if dias == 0:
        return 'hoje', dias
    if data_prazo <= hoje + timedelta(days=dias_alerta):
        return 'proximo', dias
    return 'futuro', dias


def buscar_prazos_juridicos(cursor, dias_alerta=30):
    cursor.execute("""
        SELECT
            pe.id,
            pe.processo_id,
            pe.titulo,
            pe.descricao,
            pe.data_evento,
            pe.created_at,
            p.numero_processo,
            p.titulo AS processo_titulo,
            p.status AS processo_status,
            p.fase AS processo_fase,
            p.tipo_acao
        FROM processo_eventos pe
        INNER JOIN processos p ON p.id = pe.processo_id
        WHERE pe.categoria = 'prazo'
        ORDER BY COALESCE(pe.data_evento, pe.created_at) ASC, pe.id ASC
    """)

    hoje = date.today()
    resumo = {
        'total': 0,
        'vencido': 0,
        'hoje': 0,
        'proximo': 0,
        'futuro': 0,
        'sem_data': 0,
        'alertas': 0,
    }
    prazos = []

    for row in cursor.fetchall():
        data_prazo = extrair_data_prazo(row.get('data_evento'), row.get('titulo'), row.get('descricao'))
        situacao, dias = classificar_prazo(data_prazo, hoje=hoje, dias_alerta=dias_alerta)

        row['data_prazo'] = data_prazo
        row['situacao'] = situacao
        row['dias'] = dias

        resumo['total'] += 1
        resumo[situacao] += 1
        if situacao in {'vencido', 'hoje', 'proximo'}:
            resumo['alertas'] += 1

        prazos.append(row)

    ordem = {'vencido': 0, 'hoje': 1, 'proximo': 2, 'sem_data': 3, 'futuro': 4}
    prazos.sort(key=lambda item: (
        ordem.get(item['situacao'], 9),
        item['data_prazo'] or date.max,
        item.get('numero_processo') or '',
    ))

    return prazos, resumo


def filtrar_prazos(prazos, filtro):
    if filtro == 'alertas':
        return [prazo for prazo in prazos if prazo['situacao'] in {'vencido', 'hoje', 'proximo'}]
    if filtro in {'vencido', 'hoje', 'proximo', 'futuro', 'sem_data'}:
        return [prazo for prazo in prazos if prazo['situacao'] == filtro]
    return prazos
