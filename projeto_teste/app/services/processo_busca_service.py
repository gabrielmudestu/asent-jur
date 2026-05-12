def _somente_digitos(valor):
    return ''.join(caractere for caractere in (valor or '') if caractere.isdigit())


def _montar_filtros_processos(termo_busca=None):
    termo = (termo_busca or '').strip()
    filtros = []
    parametros = []

    if termo:
        like = f"%{termo}%"
        filtros.append("""
            (
                p.numero_processo LIKE %s
                OR p.titulo LIKE %s
                OR p.descricao LIKE %s
                OR p.tipo_acao LIKE %s
                OR p.tipo_processo LIKE %s
                OR p.tribunal LIKE %s
                OR p.vara LIKE %s
                OR p.comarca LIKE %s
                OR p.status LIKE %s
                OR p.fase LIKE %s
                OR p.assunto_judicial LIKE %s
                OR EXISTS (
                    SELECT 1
                    FROM processo_partes pp
                    WHERE pp.processo_id = p.id
                      AND pp.papel IN ('cliente', 'adversa')
                      AND (
                          pp.nome LIKE %s
                          OR pp.tipo_parte LIKE %s
                          OR pp.contato LIKE %s
                          OR pp.observacoes LIKE %s
                      )
                )
                OR EXISTS (
                    SELECT 1
                    FROM processo_eventos pe
                    WHERE pe.processo_id = p.id
                      AND pe.categoria <> 'historico'
                      AND (
                          pe.categoria LIKE %s
                          OR pe.titulo LIKE %s
                          OR pe.descricao LIKE %s
                      )
                )
            )
        """)
        parametros.extend([like] * 18)

        digitos = _somente_digitos(termo)
        if digitos:
            filtros.append("""
                REPLACE(
                    REPLACE(
                        REPLACE(
                            REPLACE(COALESCE(p.numero_processo, ''), '.', ''),
                            '-',
                            ''
                        ),
                        '/',
                        ''
                    ),
                    ' ',
                    ''
                ) LIKE %s
            """)
            parametros.append(f"%{digitos}%")

    where_sql = ""
    if filtros:
        where_sql = "\nWHERE " + "\n   OR ".join(filtros)

    return where_sql, parametros


def contar_processos_juridicos(cursor, termo_busca=None):
    where_sql, parametros = _montar_filtros_processos(termo_busca)
    cursor.execute(f"SELECT COUNT(*) AS total FROM processos p {where_sql}", parametros)
    resultado = cursor.fetchone() or {}
    return int(resultado.get('total') or 0)


def buscar_processos_juridicos(cursor, termo_busca=None, limite=None, offset=0):
    campos_select = """
        SELECT
            p.id,
            p.numero_processo,
            p.titulo,
            p.descricao,
            p.tipo_acao,
            p.tipo_processo,
            p.tribunal,
            p.vara,
            p.comarca,
            p.status,
            p.fase,
            p.assunto_judicial,
            p.valor_da_causa,
            p.recurso_acionado,
            p.tipo_recurso,
            (
                SELECT pp.nome
                FROM processo_partes pp
                WHERE pp.processo_id = p.id
                  AND pp.papel = 'cliente'
                ORDER BY pp.id
                LIMIT 1
            ) AS parte_cliente,
            (
                SELECT pp.nome
                FROM processo_partes pp
                WHERE pp.processo_id = p.id
                  AND pp.papel = 'adversa'
                ORDER BY pp.id
                LIMIT 1
            ) AS parte_adversa
        FROM processos p
    """
    where_sql, parametros = _montar_filtros_processos(termo_busca)
    query = campos_select
    query += where_sql
    query += "\nORDER BY p.numero_processo"

    if limite:
        query += "\nLIMIT %s"
        parametros.append(int(limite))
        if offset:
            query += " OFFSET %s"
            parametros.append(int(offset))

    cursor.execute(query, parametros)
    return cursor.fetchall()
