import re
from datetime import date
from decimal import Decimal, InvalidOperation

from app.constants import colunas_map, imovel_opcoes, ramo_de_atividade_opcoes, status_de_assentamento_opcoes


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
    CNJ_PATTERN = re.compile(r'^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$')
    DATA_BR_PATTERN = re.compile(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b')
    DATA_ISO_PATTERN = re.compile(r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b')
    TIPO_RECURSO_OPCOES = {'apelacao', 'agravo', 'embargos', 'recurso_especial', 'recurso_extraordinario'}
    FORM_TO_DB = {form_name: db_name for form_name, db_name in colunas_map.items()}
    DB_TO_FORM = {db_name: form_name for form_name, db_name in colunas_map.items()}

    @staticmethod
    def _parse_int(value, field_name):
        if value == '':
            return 0
        if not re.fullmatch(r'\d+', value):
            raise ValueError(f'O campo "{field_name}" aceita apenas numeros inteiros.')
        return int(value)

    @staticmethod
    def _parse_decimal(value, field_name):
        if value == '':
            return Decimal('0')
        normalized = value.replace(',', '.')
        try:
            decimal_value = Decimal(normalized)
        except InvalidOperation:
            raise ValueError(f'O campo "{field_name}" aceita apenas numeros decimais validos.')
        if decimal_value < 0:
            raise ValueError(f'O campo "{field_name}" nao pode ser negativo.')
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
            raise ValueError('O CNPJ deve estar no formato 00.000.000/0000-00 ou conter 14 digitos.')

        if db_name in cls.INT_FIELDS:
            return cls._parse_int(valor, field_name)

        if db_name in cls.DECIMAL_FIELDS:
            return cls._parse_decimal(valor, field_name)

        valor_final = valor or '-'

        max_length = cls.MAX_LENGTHS.get(db_name)
        if max_length and len(valor_final) > max_length:
            raise ValueError(f'O campo "{field_name}" aceita no maximo {max_length} caracteres.')

        allowed_values = cls.ALLOWED_VALUES.get(db_name)
        if allowed_values and valor_final not in allowed_values:
            raise ValueError(f'O valor informado para "{field_name}" nao e permitido.')

        return valor_final

    @classmethod
    def normalizar_processo_juridico(cls, form):
        numero_processo = (
            form.get('numero_processo')
            or form.get('processo_judicial')
            or ''
        ).strip()
        titulo = (form.get('titulo', '') or '').strip()
        descricao = (form.get('descricao', '') or '').strip()
        tipo_acao = (form.get('tipo_acao') or form.get('tipo_processo') or '').strip()
        tribunal = (form.get('tribunal', '') or '').strip()
        vara = (form.get('vara', '') or '').strip()
        comarca = (form.get('comarca', '') or '').strip()
        status = (form.get('status', '') or '').strip()
        fase = (form.get('fase', '') or '').strip()
        data_criacao = (form.get('data_criacao', '') or '').strip() or None
        valor_da_causa = cls._parse_nullable_decimal((form.get('valor_da_causa', '') or '').strip(), 'Valor da Causa')
        recurso_acionado = bool(form.get('recurso_acionado'))
        tipo_recurso = (form.get('tipo_recurso', '') or '').strip()

        if not numero_processo:
            raise ValueError('O numero CNJ e obrigatorio.')
        if len(numero_processo) > 120:
            raise ValueError('O numero CNJ aceita no maximo 120 caracteres.')
        if not titulo:
            raise ValueError('O titulo do processo e obrigatorio.')
        if not tipo_acao:
            raise ValueError('O tipo de acao e obrigatorio.')
        if not status:
            raise ValueError('O status e obrigatorio.')
        if recurso_acionado and tipo_recurso not in cls.TIPO_RECURSO_OPCOES:
            raise ValueError('Selecione um tipo de recurso valido.')
        if not recurso_acionado:
            tipo_recurso = ''

        return {
            'numero_processo': numero_processo,
            'titulo': titulo,
            'descricao': descricao or None,
            'tipo_acao': tipo_acao,
            'tipo_processo': tipo_acao,
            'tribunal': tribunal or None,
            'vara': vara or None,
            'comarca': comarca or None,
            'status': status,
            'fase': fase or None,
            'data_criacao': data_criacao,
            'assunto_judicial': descricao or titulo,
            'valor_da_causa': valor_da_causa,
            'recurso_acionado': recurso_acionado,
            'tipo_recurso': tipo_recurso or None,
        }

    @classmethod
    def normalizar_processos_juridicos_edicao(cls, form):
        return [cls.normalizar_processo_juridico(form)]

    @staticmethod
    def linhas_textarea(valor):
        return [linha.strip() for linha in (valor or '').splitlines() if linha.strip()]

    @classmethod
    def extrair_data_evento(cls, texto):
        texto = texto or ''

        match_iso = cls.DATA_ISO_PATTERN.search(texto)
        if match_iso:
            ano, mes, dia = match_iso.groups()
            try:
                return date(int(ano), int(mes), int(dia)).isoformat()
            except ValueError:
                return None

        match_br = cls.DATA_BR_PATTERN.search(texto)
        if match_br:
            dia, mes, ano = match_br.groups()
            ano = int(ano)
            if ano < 100:
                ano = 2000 + ano if ano < 70 else 1900 + ano
            try:
                return date(ano, int(mes), int(dia)).isoformat()
            except ValueError:
                return None

        return None

    @classmethod
    def normalizar_vinculos_processo(cls, form):
        partes = []

        parte_cliente = (form.get('parte_cliente', '') or '').strip()
        if parte_cliente:
            partes.append({
                'papel': 'cliente',
                'nome': parte_cliente,
                'tipo_parte': (form.get('tipo_parte_cliente', '') or '').strip() or None,
                'contato': (form.get('contato_parte_cliente', '') or '').strip() or None,
                'observacoes': None,
            })

        parte_adversa = (form.get('parte_adversa', '') or '').strip()
        if parte_adversa:
            partes.append({
                'papel': 'adversa',
                'nome': parte_adversa,
                'tipo_parte': (form.get('tipo_parte_adversa', '') or '').strip() or None,
                'contato': (form.get('contato_parte_adversa', '') or '').strip() or None,
                'observacoes': None,
            })

        for linha in cls.linhas_textarea(form.get('outras_partes', '')):
            partes.append({
                'papel': 'outra',
                'nome': linha,
                'tipo_parte': None,
                'contato': None,
                'observacoes': None,
            })

        eventos = []
        for campo, categoria in [
            ('prazos', 'prazo'),
            ('movimentacoes', 'movimentacao'),
            ('documentos', 'documento'),
        ]:
            for linha in cls.linhas_textarea(form.get(campo, '')):
                eventos.append({
                    'categoria': categoria,
                    'titulo': None,
                    'descricao': linha,
                    'data_evento': cls.extrair_data_evento(linha) if categoria == 'prazo' else None,
                })

        return partes, eventos
