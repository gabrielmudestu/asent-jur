COLUNAS = [
    'municipio', 'distrito', 'empresa', 'cnpj',
    'processo_sei', 'status_de_assentamento', 'observacoes',
    'ramo_de_atividade', 'empregos_gerados', 'observacoes_1',
    'quadra', 'modulo_s', 'qtd_modulos', 'tamanho_m2',
    'matricula_s', 'obsevacoes', 'data_escrituracao',
    'data_contrato_de_compra_e_venda', 'acao_judicial',
    'taxa_e_ocupacao_do_imovel', 'imovel_regular_irregular',
    'irregularidades', 'ultima_vistoria', 'observacoes_2',
    'atualizado', 'observacoes_3', 'processo_judicial',
    'status', 'assunto_judicial', 'valor_da_causa',
]

LABELS = {
    'municipio': 'Município',
    'distrito': 'Distrito',
    'empresa': 'Empresa',
    'cnpj': 'CNPJ',
    'processo_sei': 'Processo SEI',
    'status_de_assentamento': 'Status de Assentamento',
    'observacoes': 'Observações',
    'ramo_de_atividade': 'Ramo de Atividade',
    'empregos_gerados': 'Empregos Gerados',
    'observacoes_1': 'Observações 1',
    'quadra': 'Quadra',
    'modulo_s': 'Módulo(s)',
    'qtd_modulos': 'Quantidade de Módulos',
    'tamanho_m2': 'Tamanho (m²)',
    'matricula_s': 'Matrícula(s)',
    'obsevacoes': 'Observações',
    'data_escrituracao': 'Data de Escrituração',
    'data_contrato_de_compra_e_venda': 'Data do Contrato de Compra e Venda',
    'acao_judicial': 'Ação Judicial',
    'taxa_e_ocupacao_do_imovel': 'Taxa e Ocupação do Imóvel (%)',
    'imovel_regular_irregular': 'Imóvel Regular/Irregular',
    'irregularidades': 'Irregularidades',
    'ultima_vistoria': 'Última Vistoria',
    'observacoes_2': 'Observações 2',
    'atualizado': 'Atualizado',
    'observacoes_3': 'Observações 3',
    'processo_judicial': 'Processo Judicial',
    'status': 'Status',
    'assunto_judicial': 'Assunto Judicial',
    'valor_da_causa': 'Valor da Causa',
}

#as fixas delimitam os campos relacionados ao usuários de Assentamento 
chaves_fixas = COLUNAS[:-4] 
#as editáveis indicam os campos referentes aos usuários do Jurídico
chaves_editaveis = COLUNAS[-4:]

labels_fixas = {k: LABELS[k] for k in chaves_fixas}
labels_editaveis = {k: LABELS[k] for k in chaves_editaveis}

colunas_map = {
    'MUNICIPIO': 'municipio',
    'DISTRITO': 'distrito',
    'EMPRESA': 'empresa',
    'CNPJ': 'cnpj',
    'PROCESSO SEI': 'processo_sei',
    'STATUS DE ASSENTAMENTO': 'status_de_assentamento',
    'RAMO DE ATIVIDADE': 'ramo_de_atividade',
    'EMPREGOS GERADOS': 'empregos_gerados',
    'QUADRA': 'quadra',
    'MÓDULO(S)': 'modulo_s',
    'QTD. MÓDULOS': 'qtd_modulos',
    'TAMANHO(M²)': 'tamanho_m2',
    'MATRÍCULA(S)': 'matricula_s',
    'OBSEVAÇÕES': 'obsevacoes',
    'DATA ESCRITURAÇÃO': 'data_escrituracao',
    'DATA CONTRATO DE COMPRA E VENDA': 'data_contrato_de_compra_e_venda',
    'IRREGULARIDADES?': 'irregularidades',
    'ÚLTIMA VISTORIA': 'ultima_vistoria',
    'ATUALIZADO': 'atualizado',
    'IMÓVEL REGULAR/IRREGULAR': 'imovel_regular_irregular',
    'TAXA E OCUPAÇÃO DO IMÓVEL(%)': 'taxa_e_ocupacao_do_imovel',
}

campos_numericos = ['processo_sei', 'empregos_gerados', 'quadra', 'qtd_modulos', 'tamanho_m2', 'matricula_s', 'taxa_e_ocupacao_do_imovel']