import re
from decimal import Decimal, InvalidOperation

from app.constants import colunas_map, imovel_opcoes, ramo_de_atividade_opcoes, status_de_assentamento_opcoes, status_opcoes


class CadastroService:
    INT_FIELDS = {'processo_sei', 'empregos_gerados', 'quadra', 'qtd_modulos', 'matricula_s'}
    DECIMAL_FIELDS = {'tamanho_m2', 'taxa_e_ocupacao_do_imovel'}
    MAX_LENGTHS = {
        'municipio': 50,
        'distrito': 50,
        'empresa': 50,
        'cnpj': 50,
        'status_de_assentamento': 50,
        'ramo_de_atividade': 50,
        'modulo_s': 50,
        'obsevacoes': 50,
        'data_escrituracao': 50,
        'data_contrato_de_compra_e_venda': 50,
        'imovel_regular_irregular': 50,
        'irregularidades': 50,
        'ultima_vistoria': 50,
        'atualizado': 50,
    }
    ALLOWED_VALUES = {
        'ramo_de_atividade': set(ramo_de_atividade_opcoes) | {'-'},
        'status_de_assentamento': set(status_de_assentamento_opcoes) | {'-'},
        'imovel_regular_irregular': set(imovel_opcoes) | {'-'},
    }
    CNPJ_PATTERN = re.compile(r'^(?:\d{14}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})$')
    PROCESSO_TIPO_OPCOES = {'trabalhista', 'civel', 'criminal'}
    TIPO_RECURSO_OPCOES = {'apelacao', 'agravo', 'embargos', 'recurso_especial', 'recurso_extraordinario'}
    FORM_TO_DB = {form_name: db_name for form_name, db_name in colunas_map.items()}
    DB_TO_FORM = {db_name: form_name for form_name, db_name in colunas_map.items()}

    @staticmethod
    def _parse_int(value, field_name):
        if value == '':
            return 0
        if not re.fullmatch(r'\d+', value):
            raise ValueError(f'O campo "{field_name}" aceita apenas números inteiros.')
        return int(value)

    @staticmethod
    def _parse_decimal(value, field_name):
        if value == '':
            return Decimal('0')
        normalized = value.replace(',', '.')
        try:
            decimal_value = Decimal(normalized)
        except InvalidOperation:
            raise ValueError(f'O campo "{field_name}" aceita apenas números decimais válidos.')
        if decimal_value < 0:
            raise ValueError(f'O campo "{field_name}" não pode ser negativo.')
        return decimal_value.quantize(Decimal('0.01'))

    @staticmethod
    def _parse_nullable_decimal(value, field_name):
        if value == '':
            return None
        return CadastroService._parse_decimal(value, field_name)

    @classmethod
    def normalizar_dados(cls, form):
        dados = {}

        for form_name, db_name in colunas_map.items():
            dados[db_name] = cls._normalizar_valor(db_name, form.get(form_name, ''), form_name)

        return dados

    @classmethod
    def normalizar_dados_edicao(cls, form, campos):
        dados = {}
        for db_name in campos:
            form_name = cls.DB_TO_FORM.get(db_name, db_name)
            dados[db_name] = cls._normalizar_valor(db_name, form.get(db_name, ''), form_name)
        return dados

    @classmethod
    def _normalizar_valor(cls, db_name, raw_value, field_name):
        valor = (raw_value or '').strip()

        if db_name == 'cnpj' and valor and not cls.CNPJ_PATTERN.fullmatch(valor):
            raise ValueError('O CNPJ deve estar no formato 00.000.000/0000-00 ou conter 14 dígitos.')

        if db_name in cls.INT_FIELDS:
            return cls._parse_int(valor, field_name)

        if db_name in cls.DECIMAL_FIELDS:
            return cls._parse_decimal(valor, field_name)

        valor_final = valor or '-'

        max_length = cls.MAX_LENGTHS.get(db_name)
        if max_length and len(valor_final) > max_length:
            raise ValueError(f'O campo "{field_name}" aceita no máximo {max_length} caracteres.')

        allowed_values = cls.ALLOWED_VALUES.get(db_name)
        if allowed_values and valor_final not in allowed_values:
            raise ValueError(f'O valor informado para "{field_name}" não é permitido.')

        return valor_final

    @classmethod
    def normalizar_processo_juridico(cls, form):
        numero_processo = (form.get('processo_judicial', '') or '').strip()
        tipo_processo = (form.get('tipo_processo', '') or '').strip()
        status = (form.get('status', '') or '').strip()
        assunto_judicial = (form.get('assunto_judicial', '') or '').strip()
        valor_da_causa = cls._parse_nullable_decimal((form.get('valor_da_causa', '') or '').strip(), 'Valor da Causa')
        recurso_acionado = bool(form.get('recurso_acionado'))
        tipo_recurso = (form.get('tipo_recurso', '') or '').strip()

        if not numero_processo:
            raise ValueError('O número do processo é obrigatório.')
        if len(numero_processo) > 120:
            raise ValueError('O número do processo aceita no máximo 120 caracteres.')
        if tipo_processo not in cls.PROCESSO_TIPO_OPCOES:
            raise ValueError('Selecione um tipo de processo válido.')
        if status not in status_opcoes:
            raise ValueError('Selecione um status válido.')
        if not assunto_judicial:
            raise ValueError('O assunto judicial é obrigatório.')
        if recurso_acionado:
            if tipo_recurso not in cls.TIPO_RECURSO_OPCOES:
                raise ValueError('Selecione um tipo de recurso válido.')
        else:
            tipo_recurso = ''

        return {
            'numero_processo': numero_processo,
            'tipo_processo': tipo_processo,
            'status': status,
            'assunto_judicial': assunto_judicial,
            'valor_da_causa': valor_da_causa,
            'recurso_acionado': recurso_acionado,
            'tipo_recurso': tipo_recurso or None,
        }

    @classmethod
    def normalizar_processos_juridicos_edicao(cls, form):
        numeros = form.getlist("numero_processo[]")
        tipos = form.getlist("tipo_processo[]")
        status_list = form.getlist("status[]")
        assuntos = form.getlist("assunto_judicial[]")
        valores = form.getlist("valor_da_causa[]")
        recursos_acionados = form.getlist("recurso_acionado[]")
        tipos_recurso = form.getlist("tipo_recurso[]")

        processos = []
        for i in range(len(numeros)):
            numero = (numeros[i] or '').strip()
            if not numero:
                continue

            tipo_processo = (tipos[i] or '').strip() if i < len(tipos) else ''
            status = (status_list[i] or '').strip() if i < len(status_list) else ''
            assunto = (assuntos[i] or '').strip() if i < len(assuntos) else ''
            valor = (valores[i] or '').strip() if i < len(valores) else ''
            recurso_acionado = recursos_acionados[i] == '1' if i < len(recursos_acionados) else False
            tipo_recurso = (tipos_recurso[i] or '').strip() if i < len(tipos_recurso) else ''

            processo = cls.normalizar_processo_juridico({
                'processo_judicial': numero,
                'tipo_processo': tipo_processo,
                'status': status,
                'assunto_judicial': assunto,
                'valor_da_causa': valor,
                'recurso_acionado': '1' if recurso_acionado else '',
                'tipo_recurso': tipo_recurso,
            })
            processos.append(processo)

        return processos
