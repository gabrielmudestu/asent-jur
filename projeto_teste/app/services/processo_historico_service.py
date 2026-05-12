import re
from datetime import date
from decimal import Decimal


DATA_ISO_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')


CAMPOS_PROCESSO_LABELS = {
    'numero_processo': 'Numero CNJ',
    'titulo': 'Titulo',
    'descricao': 'Descricao',
    'tipo_acao': 'Tipo de acao',
    'tipo_processo': 'Tipo de processo',
    'tribunal': 'Tribunal',
    'vara': 'Vara',
    'comarca': 'Comarca',
    'valor_da_causa': 'Valor da causa',
    'status': 'Status',
    'fase': 'Fase',
    'data_criacao': 'Data de criacao',
    'assunto_judicial': 'Assunto judicial',
    'recurso_acionado': 'Recurso acionado',
    'tipo_recurso': 'Tipo de recurso',
}


def valor_legivel(valor):
    if valor in (None, ''):
        return '-'
    if isinstance(valor, Decimal):
        return str(valor.quantize(Decimal('0.01')))
    if isinstance(valor, date):
        return valor.strftime('%d/%m/%Y')
    if isinstance(valor, str) and DATA_ISO_PATTERN.fullmatch(valor):
        ano, mes, dia = valor.split('-')
        return f"{dia}/{mes}/{ano}"
    if isinstance(valor, bool):
        return 'Sim' if valor else 'Nao'
    if isinstance(valor, int) and valor in (0, 1):
        return 'Sim' if valor else 'Nao'
    return str(valor)


def valor_comparavel(valor):
    if valor in (None, ''):
        return ''
    if isinstance(valor, Decimal):
        return str(valor.quantize(Decimal('0.01')))
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, bool):
        return '1' if valor else '0'
    if isinstance(valor, int) and valor in (0, 1):
        return str(valor)
    return str(valor).strip()


def registrar_historico_processo(cursor, processo_id, titulo, descricao):
    cursor.execute("""
        INSERT INTO processo_eventos
        (processo_id, categoria, titulo, descricao, data_evento)
        VALUES (%s, 'historico', %s, %s, CURDATE())
    """, (processo_id, titulo, descricao))


def historico_criacao_manual(usuario, processo):
    return (
        'Criacao manual',
        (
            f"Processo criado manualmente por {usuario}. "
            f"Numero CNJ: {valor_legivel(processo.get('numero_processo'))}. "
            f"Titulo: {valor_legivel(processo.get('titulo'))}. "
            f"Status inicial: {valor_legivel(processo.get('status'))}."
        )
    )


def historico_importacao(usuario, processo, nome_arquivo, linha):
    return (
        'Importacao de planilha',
        (
            f"Processo importado por {usuario}. "
            f"Arquivo: {nome_arquivo or '-'}. Linha da planilha: {linha}. "
            f"Numero CNJ: {valor_legivel(processo.get('numero_processo'))}. "
            f"Titulo: {valor_legivel(processo.get('titulo'))}."
        )
    )


def historico_importacao_duplicada(usuario, numero_processo, nome_arquivo, linha):
    return (
        'Importacao duplicada ignorada',
        (
            f"Tentativa de importacao duplicada ignorada por {usuario}. "
            f"Arquivo: {nome_arquivo or '-'}. Linha da planilha: {linha}. "
            f"Numero CNJ ja existente: {valor_legivel(numero_processo)}."
        )
    )


def historico_documento_anexado(usuario, nome_documento=None, origem='edicao'):
    return (
        'Documento anexado',
        (
            f"Documento anexado por {usuario} durante {origem}. "
            f"Nome informado: {valor_legivel(nome_documento)}."
        )
    )


def _normalizar_lista_partes(partes):
    return sorted(
        (
            valor_comparavel(parte.get('papel')),
            valor_comparavel(parte.get('nome')),
            valor_comparavel(parte.get('tipo_parte')),
            valor_comparavel(parte.get('contato')),
            valor_comparavel(parte.get('observacoes')),
        )
        for parte in partes
    )


def _normalizar_lista_eventos(eventos):
    return sorted(
        (
            valor_comparavel(evento.get('categoria')),
            valor_comparavel(evento.get('titulo')),
            valor_comparavel(evento.get('descricao')),
            valor_comparavel(evento.get('data_evento')),
        )
        for evento in eventos
        if evento.get('categoria') != 'historico'
    )


def montar_alteracoes_processo(processo_antigo, processo_novo, partes_antigas=None, partes_novas=None, eventos_antigos=None, eventos_novos=None):
    alteracoes = []

    for campo, label in CAMPOS_PROCESSO_LABELS.items():
        antigo_bruto = (processo_antigo or {}).get(campo)
        novo_bruto = (processo_novo or {}).get(campo)
        if valor_comparavel(antigo_bruto) != valor_comparavel(novo_bruto):
            alteracoes.append(f"{label}: '{valor_legivel(antigo_bruto)}' -> '{valor_legivel(novo_bruto)}'")

    if _normalizar_lista_partes(partes_antigas or []) != _normalizar_lista_partes(partes_novas or []):
        alteracoes.append('Partes vinculadas foram alteradas.')

    if _normalizar_lista_eventos(eventos_antigos or []) != _normalizar_lista_eventos(eventos_novos or []):
        alteracoes.append('Prazos, movimentacoes ou documentos textuais foram alterados.')

    return alteracoes


def historico_edicao(usuario, alteracoes):
    if alteracoes:
        descricao = f"Processo editado por {usuario}. Alteracoes: " + '; '.join(alteracoes)
    else:
        descricao = f"Processo editado por {usuario}. Nenhuma alteracao de dados identificada."
    return 'Edicao de processo', descricao
