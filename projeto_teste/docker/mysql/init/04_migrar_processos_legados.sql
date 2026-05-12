INSERT INTO processos (
    empresa_id,
    numero_processo,
    titulo,
    descricao,
    tipo_acao,
    tipo_processo,
    status,
    assunto_judicial,
    valor_da_causa
)
SELECT
    NULL,
    TRIM(ml.processo_judicial),
    TRIM(ml.processo_judicial),
    NULLIF(TRIM(ml.assunto_judicial), '-'),
    'civel',
    'civel',
    CASE
        WHEN UPPER(TRIM(ml.status)) IN ('ATIVO', 'ARQUIVADO', 'SUSPENSO') THEN UPPER(TRIM(ml.status))
        ELSE 'ATIVO'
    END,
    NULLIF(TRIM(ml.assunto_judicial), '-'),
    CASE
        WHEN REPLACE(TRIM(ml.valor_da_causa), ',', '.') REGEXP '^[0-9]+(\\.[0-9]+)?$'
            THEN CAST(REPLACE(TRIM(ml.valor_da_causa), ',', '.') AS DECIMAL(15, 2))
        ELSE NULL
    END
FROM municipal_lots ml
WHERE ml.processo_judicial IS NOT NULL
  AND TRIM(ml.processo_judicial) NOT IN ('', '-')
  AND NOT EXISTS (
      SELECT 1
      FROM processos p
      WHERE p.numero_processo = TRIM(ml.processo_judicial)
  );
