import os
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename


DOCUMENTO_EXTENSOES_PERMITIDAS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'docx'}


def extensao_permitida(nome_arquivo):
    return '.' in nome_arquivo and nome_arquivo.rsplit('.', 1)[1].lower() in DOCUMENTO_EXTENSOES_PERMITIDAS


def pasta_documentos_processos():
    return os.path.join(current_app.root_path, 'uploads', 'processos')


def salvar_documento_processo(cursor, processo_id, arquivo, form):
    if not arquivo or not arquivo.filename:
        return None

    if not extensao_permitida(arquivo.filename):
        raise ValueError('Anexe apenas arquivos PDF, imagem ou DOCX.')

    nome_original = secure_filename(arquivo.filename)
    extensao = nome_original.rsplit('.', 1)[1].lower()
    nome_salvo = f"processo_{processo_id}_{uuid4().hex}.{extensao}"
    pasta_destino = pasta_documentos_processos()
    os.makedirs(pasta_destino, exist_ok=True)
    caminho_arquivo = os.path.join(pasta_destino, nome_salvo)
    arquivo.save(caminho_arquivo)

    nome_documento = (form.get('documento_nome') or '').strip() or os.path.splitext(nome_original)[0]
    tipo_documento = (form.get('documento_tipo') or '').strip() or extensao.upper()
    data_documento = (form.get('documento_data') or '').strip() or None
    observacao = (form.get('documento_observacao') or '').strip() or None

    cursor.execute("""
        INSERT INTO processo_documentos
        (processo_id, nome, tipo, data_documento, observacao, nome_arquivo_original,
         nome_arquivo_salvo, caminho_arquivo, content_type, tamanho_bytes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        processo_id,
        nome_documento,
        tipo_documento,
        data_documento,
        observacao,
        nome_original,
        nome_salvo,
        caminho_arquivo,
        arquivo.mimetype,
        os.path.getsize(caminho_arquivo),
    ))
    return cursor.lastrowid
